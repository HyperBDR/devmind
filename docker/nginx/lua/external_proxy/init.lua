-- external_proxy/init.lua
-- Dynamic routing table: loads from Django API, caches in ngx.shared.DICT.
-- Refreshes every ROUTE_TTL seconds.

local cjson = require("cjson.safe")

local _M = {}

local SHARED_DICT_NAME = "external_proxy"
local CACHE_KEY = "routing_table"
local ROUTE_TTL = 30

_M.API_BASE = "http://backend-api:8000/api/v1/admin/external-proxy/internal"

local function log(level, ...)
    ngx.log(level, "[external_proxy] ", ...)
end

local DOCKER_RESOLVER = "127.0.0.11"

local function fetch_from_api()
    local http = require("resty.http")
    local httpc = http.new()
    httpc:set_timeout(3000)

    local res, err = httpc:request_uri(
        _M.API_BASE .. "/routing-config/",
        {
            method = "GET",
            resolver = {DOCKER_RESOLVER},
        }
    )
    if not res then
        log(ngx.ERR, "API fetch failed: ", err)
        return nil
    end

    if res.status ~= 200 then
        log(ngx.ERR, "API returned status ", res.status)
        return nil
    end

    -- Extract the routes array from {"routes": [...]}
    local ok, body = pcall(cjson.decode, res.body)
    if not ok or type(body) ~= "table" or type(body.routes) ~= "table" then
        log(ngx.ERR, "Invalid API response format")
        return nil
    end

    return cjson.encode(body.routes)
end

local function refresh()
    local json_body = fetch_from_api()
    if not json_body then
        return false
    end

    local dict = ngx.shared[SHARED_DICT_NAME]
    if dict then
        dict:set(CACHE_KEY, json_body)
    end

    return true
end

-- Deferred init: runs in timer context where resty.http is available
local function deferred_init(premature)
    if premature then return end
    if refresh() then
        log(ngx.INFO, "routing table loaded")
    else
        log(ngx.WARN, "init: no routing config available")
    end
end

function _M.init()
    -- Load immediately via a zero-delay timer (works in init_worker context)
    local ok, err = ngx.timer.at(0, deferred_init)
    if not ok then
        log(ngx.ERR, "failed to schedule init: ", err)
    end
end

function _M.start_refresh()
    local ok, err = ngx.timer.every(ROUTE_TTL, function(premature)
        if premature then return end
        refresh()
    end)
    if not ok then
        log(ngx.ERR, "failed to start refresh timer: ", err)
    end
end

function _M.match(slug)
    local dict = ngx.shared[SHARED_DICT_NAME]
    if not dict then
        return nil
    end

    local json_body = dict:get(CACHE_KEY)
    if not json_body then
        return nil
    end

    local ok, data = pcall(cjson.decode, json_body)
    if not ok or type(data) ~= "table" then
        log(ngx.ERR, "JSON parse failed")
        return nil
    end

    for _, route in ipairs(data) do
        if route.slug == slug then
            return route
        end
    end
    return nil
end

return _M
