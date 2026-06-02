-- resty/hmac.lua
-- Minimal HMAC-SHA256 using OpenResty's bundled OpenSSL FFI.
local ffi = require "ffi"
local C = ffi.C

ffi.cdef[[
typedef struct engine_st ENGINE;
typedef struct hmac_ctx_st HMAC_CTX;
typedef struct evp_md_ctx_st EVP_MD_CTX;
typedef struct evp_md_st EVP_MD;

HMAC_CTX *HMAC_CTX_new(void);
void HMAC_CTX_free(HMAC_CTX *ctx);
int HMAC_Init_ex(HMAC_CTX *ctx, const void *key, int len, const EVP_MD *md, ENGINE *impl);
int HMAC_Update(HMAC_CTX *ctx, const unsigned char *data, int len);
int HMAC_Final(HMAC_CTX *ctx, unsigned char *md, unsigned int *len);
const EVP_MD *EVP_sha256(void);
]]

local _M = {}
local mt = { __index = _M }

local SHA256_LEN = 32

function _M.new(_, key)
    if not key then
        return nil, "key is required"
    end
    local ctx = C.HMAC_CTX_new()
    if ctx == nil then
        return nil, "HMAC_CTX_new failed"
    end
    local ok = C.HMAC_Init_ex(ctx, key, #key, C.EVP_sha256(), nil)
    if ok ~= 1 then
        C.HMAC_CTX_free(ctx)
        return nil, "HMAC_Init_ex failed"
    end
    return setmetatable({ _ctx = ctx }, mt)
end

-- Alias for bungle/lua-resty-hmac compatibility
_M.ALGOS = { SHA256 = "sha256" }

function _M.update(self, data)
    local ok = C.HMAC_Update(self._ctx, data, #data)
    if ok ~= 1 then
        return nil, "HMAC_Update failed"
    end
    return true
end

function _M.final(self)
    local buf = ffi.new("unsigned char[?]", SHA256_LEN)
    local len = ffi.new("unsigned int[1]")
    local ok = C.HMAC_Final(self._ctx, buf, len)
    if ok ~= 1 then
        return nil, "HMAC_Final failed"
    end
    C.HMAC_CTX_free(self._ctx)
    self._ctx = nil
    return ffi.string(buf, len[0])
end

return _M
