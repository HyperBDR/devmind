-- external_proxy/access.lua
-- Returns a module with run() and proxy_request() functions.

local proxy = require("external_proxy.init")
local cjson = require("cjson.safe")

local _M = {}

local function hex_encode(value)
    return (value:gsub(".", function(char)
        return string.format("%02x", string.byte(char))
    end))
end

local function read_request_body(method)
    if method == "GET" or method == "HEAD" then
        return nil
    end

    ngx.req.read_body()

    local body = ngx.req.get_body_data()
    if body then
        return body
    end

    local body_file = ngx.req.get_body_file()
    if not body_file then
        return nil
    end

    local file, err = io.open(body_file, "rb")
    if not file then
        return nil, "failed to read request body file: " .. (err or "unknown")
    end

    body = file:read("*a")
    file:close()
    return body
end

-- Phase 1: access_by_lua — verify auth, set variables
function _M.run()
    local slug = ngx.var.uri:match("^/proxy/([%w_-]+)/")
    if not slug then
        ngx.status = 404
        ngx.say("Not found")
        return ngx.exit(404)
    end

    local route = proxy.match(slug)
    if not route then
        ngx.status = 404
        ngx.say("Site not configured or inactive")
        return ngx.exit(404)
    end

    if route.access_mode ~= "proxy" then
        ngx.status = 400
        ngx.say("This site uses " .. route.access_mode .. " mode")
        return ngx.exit(400)
    end

    -- Auth check via Django
    local feature = route.required_feature or ""
    if feature ~= "" then
        local http = require("resty.http")
        local httpc = http.new()
        httpc:set_timeout(3000)

        local req_headers = {
            ["Authorization"] = ngx.var.http_authorization or "",
            ["Cookie"] = ngx.var.http_cookie or "",
        }

        local res, err = httpc:request_uri(
            proxy.API_BASE .. "/auth-check/"
                .. "?feature=" .. ngx.escape_uri(feature),
            {
                method = "GET",
                headers = req_headers,
                resolver = {"127.0.0.11"},
            }
        )
        if not res then
            ngx.status = 502
            ngx.say("Auth service unavailable")
            return ngx.exit(502)
        end

        if res.status ~= 200 then
            ngx.status = res.status
            ngx.say(res.body or "Access denied")
            return ngx.exit(res.status)
        end
    end

    -- Store route info in nginx variables for proxy_request phase
    ngx.var.proxy_prefix = "/proxy/" .. slug .. "/"
    ngx.ctx.route = route
    ngx.ctx.slug = slug
end

-- Phase 2: content_by_lua — make the actual proxy request
function _M.proxy_request()
    local route = ngx.ctx.route
    if not route then
        ngx.status = 500
        ngx.say("Internal error: no route context")
        return ngx.exit(500)
    end

    local slug = ngx.ctx.slug
    local target_host = route.target_host
    local target_scheme = route.target_scheme or "http"

    -- Parse host:port
    local host, port = target_host:match("^(.-):(%d+)$")
    if not host then
        host = target_host
        if target_scheme == "https" then
            port = 443
        else
            port = 80
        end
    else
        port = tonumber(port)
    end

    -- Build target URL
    local relative_path = ngx.var.uri:match("^/proxy/[%w_-]+/(.*)$") or ""
    local target_url = target_scheme .. "://" .. host .. ":" .. port .. "/" .. relative_path
    local query = ngx.var.args
    if query and query ~= "" then
        target_url = target_url .. "?" .. query
    end

    -- Forward headers
    local headers = {}
    for k, v in pairs(ngx.req.get_headers()) do
        local lk = k:lower()
        if lk ~= "host" and lk ~= "connection" and lk ~= "transfer-encoding" then
            headers[k] = v
        end
    end
    headers["Host"] = host
    headers["X-Forwarded-Host"] = ngx.var.host
    headers["X-Forwarded-Proto"] = ngx.var.scheme
    headers["X-Forwarded-Prefix"] = ngx.var.proxy_prefix
    headers["Accept-Encoding"] = ""  -- disable compression for sub_filter

    -- S2S auth headers
    if route.auth_type == "static_token" then
        if not route.static_token or route.static_token == "" then
            ngx.status = 502
            ngx.say("Proxy static token is not configured")
            return ngx.exit(502)
        end
        headers["Authorization"] = "Bearer " .. route.static_token
    elseif route.auth_type == "hmac" then
        if not route.hmac_secret or route.hmac_secret == "" then
            ngx.status = 502
            ngx.say("Proxy HMAC secret is not configured")
            return ngx.exit(502)
        end
        local hmac_mod = require("resty.hmac")
        local timestamp = tostring(ngx.time())
        local nonce = timestamp .. "-" .. ngx.var.request_id
        local site_id = route.id or slug
        local message = tostring(site_id) .. "|" .. ngx.var.uri .. "|" .. nonce
        local h = hmac_mod.new(nil, route.hmac_secret)
        if h then
            h:update(message)
            headers["X-External-Site-ID"] = tostring(site_id)
            headers["X-Request-Path"] = ngx.var.uri
            headers["X-Timestamp"] = timestamp
            headers["X-Nonce"] = nonce
            headers["X-Signature"] = hex_encode(h:final())
        else
            ngx.status = 502
            ngx.say("Proxy auth configuration error")
            return ngx.exit(502)
        end
    elseif route.auth_type == "token_fetch" then
        local http = require("resty.http")
        local httpc = http.new()
        httpc:set_timeout(3000)
        local res, err = httpc:request_uri(
            proxy.API_BASE .. "/auth-token/"
                .. "?slug=" .. ngx.escape_uri(slug)
                .. "&path=" .. ngx.escape_uri(ngx.var.uri),
            {method = "GET", resolver = {"127.0.0.11"}}
        )
        if res and res.status == 200 then
            local data = cjson.decode(res.body)
            local has_auth = false
            if data and data.authorization and data.authorization ~= "" then
                headers["Authorization"] = data.authorization
                has_auth = true
            end
            if data and data.headers then
                for k, v in pairs(data.headers) do
                    headers[k] = v
                    has_auth = true
                end
            end
            if not has_auth then
                ngx.status = 502
                ngx.say("Proxy auth token unavailable")
                return ngx.exit(502)
            end
        else
            ngx.status = 502
            ngx.say("Proxy auth token unavailable")
            return ngx.exit(502)
        end
    end

    -- Make the proxy request
    local http = require("resty.http")
    local httpc = http.new()
    httpc:set_timeout(30000)

    local method = ngx.req.get_method()
    local body, body_err = read_request_body(method)
    if body_err then
        ngx.status = 400
        ngx.say(body_err)
        return ngx.exit(400)
    end

    -- ssl_verify is only meaningful for https upstreams. Default to true
    -- (verify the upstream's certificate); admins explicitly opt out per
    -- site via verify_tls when the target uses a self-signed cert.
    local ssl_verify
    if target_scheme == "https" then
        ssl_verify = route.verify_tls
        if ssl_verify == nil then
            ssl_verify = true
        end
    else
        ssl_verify = false
    end

    local res, err = httpc:request_uri(target_url, {
        method = method,
        headers = headers,
        body = body,
        ssl_verify = ssl_verify,
        ssl_server_name = host,
        resolver = {"127.0.0.11"},
    })

    if not res then
        ngx.status = 502
        ngx.say("Proxy error: " .. (err or "unknown"))
        return ngx.exit(502)
    end

    -- Set response status
    ngx.status = res.status

    -- Copy response headers (skip hop-by-hop)
    local skip = {
        ["transfer-encoding"] = true,
        ["connection"] = true,
        ["content-encoding"] = true,
        ["content-length"] = true,
    }
    for k, v in pairs(res.headers) do
        if not skip[k:lower()] then
            ngx.header[k] = v
        end
    end

    -- Rewrite paths in HTML/CSS/JS responses
    local prefix = ngx.var.proxy_prefix
    local ct = res.headers["Content-Type"] or res.headers["content-type"] or ""
    local body_str = res.body or ""

    if ct:find("text/html") or ct:find("text/css")
        or ct:find("javascript") or ct:find("text/xml") then
        body_str = body_str:gsub('href="/', 'href="' .. prefix)
        body_str = body_str:gsub('src="/', 'src="' .. prefix)
        body_str = body_str:gsub('action="/', 'action="' .. prefix)
        body_str = body_str:gsub("href='/", "href='" .. prefix)
        body_str = body_str:gsub("src='/", "src='" .. prefix)
        body_str = body_str:gsub("url%(/", "url(" .. prefix)
    end

    ngx.header["Content-Length"] = #body_str
    ngx.print(body_str)
end

return _M
