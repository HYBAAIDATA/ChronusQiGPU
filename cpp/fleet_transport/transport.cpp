// Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
// Native bounded HTTP transport. Authentication decisions remain in FleetAuth.
#include <curl/curl.h>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <memory>
#include <string>
#include <string_view>

#ifdef _WIN32
#define API extern "C" __declspec(dllexport)
#else
#define API extern "C" __attribute__((visibility("default")))
#endif

namespace {
struct Reply {
    long status = 0;
    std::size_t limit = 0;
    bool failed = false;
    bool mac_seen = false;
    bool digest_seen = false;
    std::string body, mac, digest;
};
struct CurlList {
    curl_slist* head = nullptr;
    ~CurlList() { curl_slist_free_all(head); }
    bool add(const char* line) {
        curl_slist* next = curl_slist_append(head, line);
        if (!next) return false;
        head = next;
        return true;
    }
};

bool byte_count(std::size_t size, std::size_t count, std::size_t& bytes) {
    if (size && count > std::numeric_limits<std::size_t>::max() / size) return false;
    bytes = size * count;
    return true;
}

std::size_t write_body(char* ptr, std::size_t size, std::size_t count, void* opaque) noexcept {
    auto& reply = *static_cast<Reply*>(opaque);
    std::size_t bytes = 0;
    if (!byte_count(size, count, bytes) || bytes > reply.limit - reply.body.size()) {
        reply.failed = true;
        return 0;
    }
    try {
        reply.body.append(ptr, bytes);
        return bytes;
    } catch (...) {
        reply.failed = true;
        return 0;
    }
}

bool iequal(std::string_view a, std::string_view b) noexcept {
    if (a.size() != b.size()) return false;
    for (std::size_t i = 0; i < a.size(); ++i) {
        char x = a[i], y = b[i];
        if (x >= 'A' && x <= 'Z') x = static_cast<char>(x + ('a' - 'A'));
        if (y >= 'A' && y <= 'Z') y = static_cast<char>(y + ('a' - 'A'));
        if (x != y) return false;
    }
    return true;
}
std::string_view trim(std::string_view s) noexcept {
    while (!s.empty() && (s.front() == ' ' || s.front() == '\t')) s.remove_prefix(1);
    while (!s.empty() && (s.back() == ' ' || s.back() == '\t' || s.back() == '\r' || s.back() == '\n'))
        s.remove_suffix(1);
    return s;
}
std::size_t write_header(char* ptr, std::size_t size, std::size_t count, void* opaque) noexcept {
    auto& reply = *static_cast<Reply*>(opaque);
    std::size_t bytes = 0;
    if (!byte_count(size, count, bytes)) return 0;
    try {
        const std::string_view line(ptr, bytes);
        // An informational response is not the final authenticated response.
        if (line.substr(0, 5) == "HTTP/") {
            reply.mac.clear(); reply.digest.clear();
            reply.mac_seen = false; reply.digest_seen = false;
            return bytes;
        }
        const auto colon = line.find(':');
        if (colon == std::string_view::npos) return bytes;
        const auto key = line.substr(0, colon);
        const auto val = trim(line.substr(colon + 1));
        if (iequal(key, "X-Chronus-Fleet-MAC")) {
            if (reply.mac_seen || val.size() != 64) return 0;
            reply.mac_seen = true;
            reply.mac.assign(val);
        } else if (iequal(key, "X-Chronus-Fleet-Body-SHA256")) {
            if (reply.digest_seen || val.size() != 64) return 0;
            reply.digest_seen = true;
            reply.digest.assign(val);
        }
        return bytes;
    } catch (...) {
        reply.failed = true;
        return 0;
    }
}
bool clean_header(const char* line) {
    if (!line) return false;
    for (const unsigned char* p = reinterpret_cast<const unsigned char*>(line); *p; ++p)
        if (*p < 32 || *p == 127) return false;
    return true;
}
} // namespace

API int chronus_fleet_transport_abi() { return 1; }

// Returns null on any transport, TLS, response-limit or allocation failure.
// No automatic fallback or replay of an ambiguous POST at the application layer.
API Reply* chronus_fleet_http(const char* url, const char* method,
                             const char* const* headers, std::size_t nheaders,
                             const char* body, std::size_t body_size,
                             const char* ca, long timeout_ms, std::size_t limit) noexcept {
    try {
        if (!url || !method || !body || !headers || !limit || timeout_ms <= 0 ||
            body_size > static_cast<std::size_t>(std::numeric_limits<curl_off_t>::max()) ||
            nheaders > 32) return nullptr;
        const std::string_view verb(method);
        if (verb != "GET" && verb != "POST") return nullptr;
        const std::string_view endpoint(url);
        if (endpoint.substr(0, 8) != "https://" && endpoint.substr(0, 7) != "http://") return nullptr;
        static const CURLcode initialized = curl_global_init(CURL_GLOBAL_DEFAULT);
        if (initialized != CURLE_OK) return nullptr;
        std::unique_ptr<CURL, decltype(&curl_easy_cleanup)> handle(curl_easy_init(), curl_easy_cleanup);
        if (!handle) return nullptr;
        CurlList list;
        for (std::size_t i = 0; i < nheaders; ++i)
            if (!clean_header(headers[i]) || !list.add(headers[i])) return nullptr;
        if (!list.add("Expect:")) return nullptr;
        auto reply = std::make_unique<Reply>();
        reply->limit = limit;
        CURL* easy = handle.get();
#define SET(option, value) if (curl_easy_setopt(easy, option, value) != CURLE_OK) return nullptr
        SET(CURLOPT_URL, url);
        SET(CURLOPT_CUSTOMREQUEST, method);
        SET(CURLOPT_HTTPHEADER, list.head);
        SET(CURLOPT_POSTFIELDS, body);
        SET(CURLOPT_POSTFIELDSIZE_LARGE, static_cast<curl_off_t>(body_size));
        SET(CURLOPT_PATH_AS_IS, 1L);
        SET(CURLOPT_HTTP_VERSION, static_cast<long>(CURL_HTTP_VERSION_1_1));
        SET(CURLOPT_FOLLOWLOCATION, 0L);
        SET(CURLOPT_PROXY, "");
        SET(CURLOPT_NOSIGNAL, 1L);
        SET(CURLOPT_TIMEOUT_MS, timeout_ms);
        SET(CURLOPT_CONNECTTIMEOUT_MS, timeout_ms);
        SET(CURLOPT_FRESH_CONNECT, 1L);
        SET(CURLOPT_FORBID_REUSE, 1L);
        SET(CURLOPT_SSL_VERIFYPEER, 1L);
        SET(CURLOPT_SSL_VERIFYHOST, 2L);
        SET(CURLOPT_SSLVERSION, static_cast<long>(CURL_SSLVERSION_TLSv1_2));
        if (ca && *ca) { SET(CURLOPT_CAINFO, ca); }
#if LIBCURL_VERSION_NUM >= 0x075500
        SET(CURLOPT_PROTOCOLS_STR, "http,https");
#else
        SET(CURLOPT_PROTOCOLS, static_cast<long>(CURLPROTO_HTTP | CURLPROTO_HTTPS));
#endif
        SET(CURLOPT_WRITEFUNCTION, write_body);
        SET(CURLOPT_WRITEDATA, reply.get());
        SET(CURLOPT_HEADERFUNCTION, write_header);
        SET(CURLOPT_HEADERDATA, reply.get());
#undef SET
        if (curl_easy_perform(easy) != CURLE_OK || reply->failed ||
            curl_easy_getinfo(easy, CURLINFO_RESPONSE_CODE, &reply->status) != CURLE_OK ||
            reply->status < 100 || reply->status > 599) return nullptr;
        return reply.release();
    } catch (...) {
        return nullptr;
    }
}
API long chronus_fleet_http_status(const Reply* r) { return r->status; }
API std::size_t chronus_fleet_http_size(const Reply* r) { return r->body.size(); }
API const char* chronus_fleet_http_body(const Reply* r) { return r->body.data(); }
API const char* chronus_fleet_http_mac(const Reply* r) { return r->mac.c_str(); }
API const char* chronus_fleet_http_digest(const Reply* r) { return r->digest.c_str(); }
API void chronus_fleet_http_free(Reply* r) { delete r; }
