# ─────────────────────────────────────────────────────────
# External proxy: dynamic routing via OpenResty Lua
# Full proxy handled in Lua (resty.http) — no nginx proxy_pass.
# ─────────────────────────────────────────────────────────
location /proxy/ {
    set $proxy_prefix '';

    access_by_lua_block {
        local access = require("external_proxy.access")
        access.run()
    }

    content_by_lua_block {
        local access = require("external_proxy.access")
        access.proxy_request()
    }

    header_filter_by_lua_block {
        local loc = ngx.header["Location"]
        if loc then
            local prefix = ngx.var.proxy_prefix
            if prefix and prefix ~= "" then
                ngx.header["Location"] = loc:gsub("^/", prefix)
            end
        end
    }
}
