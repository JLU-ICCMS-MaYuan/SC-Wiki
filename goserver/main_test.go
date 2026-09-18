package main

import (
	"compress/gzip"
	"io"
	"net/http"
	"net/http/httptest"
	"strconv"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestGzipMiddlewareDropsLateContentLength(t *testing.T) {
	gin.SetMode(gin.TestMode)
	payload := strings.Repeat("response-body-", 100)

	router := gin.New()
	router.Use(gzipMiddleware)
	router.GET("/proxy", func(c *gin.Context) {
		c.Header("Content-Length", strconv.Itoa(len(payload)))
		c.String(http.StatusOK, payload)
	})

	recorder := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodGet, "/proxy", nil)
	request.Header.Set("Accept-Encoding", "gzip")
	router.ServeHTTP(recorder, request)

	if got := recorder.Header().Get("Content-Length"); got != "" {
		t.Fatalf("compressed response retained stale Content-Length %q", got)
	}
	reader, err := gzip.NewReader(recorder.Body)
	if err != nil {
		t.Fatal(err)
	}
	decompressed, err := io.ReadAll(reader)
	if err != nil {
		t.Fatal(err)
	}
	if string(decompressed) != payload {
		t.Fatalf("unexpected response body length: got %d want %d", len(decompressed), len(payload))
	}
}

func TestAdminRoutesRegisterWithoutWildcardConflict(t *testing.T) {
	gin.SetMode(gin.TestMode)
	router := gin.New()
	admin := router.Group("/api/admin")

	registerAdminRoutes(admin)
}

func TestTrustedProxyIPCannotBeOverriddenByForwardedFor(t *testing.T) {
	for _, item := range []struct{ remote, real, forwarded, expected string }{
		{"203.0.113.10:1234", "198.51.100.1", "198.51.100.2", "203.0.113.10"},
		{"127.0.0.1:1234", "203.0.113.10", "198.51.100.2", "203.0.113.10"},
	} {
		router := gin.New()
		if err := configureTrustedProxies(router, ""); err != nil {
			t.Fatal(err)
		}
		router.GET("/", func(c *gin.Context) { c.String(200, c.ClientIP()) })
		request := httptest.NewRequest("GET", "/", nil)
		request.RemoteAddr = item.remote
		request.Header.Set("X-Real-IP", item.real)
		request.Header.Set("X-Forwarded-For", item.forwarded)
		recorder := httptest.NewRecorder()
		router.ServeHTTP(recorder, request)
		if recorder.Body.String() != item.expected {
			t.Fatalf("IP=%s expected=%s", recorder.Body.String(), item.expected)
		}
	}
}
