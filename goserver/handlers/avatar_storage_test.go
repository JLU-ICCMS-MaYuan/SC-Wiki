package handlers

import (
	"bytes"
	"context"
	"errors"
	"image"
	"image/color"
	"image/png"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"

	"scwiki/server/database"
	"scwiki/server/models"
	"scwiki/server/storage"

	"github.com/gin-gonic/gin"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"
)

func TestAvatarStorageRoundTrip(t *testing.T) {
	runAvatarStorageRoundTrip(t, storage.NewLocal(t.TempDir()))
}

func TestAvatarStorageFailureCleanup(t *testing.T) {
	runAvatarStorageFailureCleanup(t, storage.NewLocal(t.TempDir()))
}

func TestAvatarStorageS3RoundTrip(t *testing.T) {
	endpoint := os.Getenv("SCWIKI_TEST_S3_ENDPOINT")
	if endpoint == "" {
		t.Skip("未配置隔离 S3 服务")
	}
	files, err := storage.NewS3(endpoint, os.Getenv("SCWIKI_TEST_S3_REGION"),
		"scwiki-storage-test", os.Getenv("SCWIKI_TEST_S3_ACCESS_KEY"),
		os.Getenv("SCWIKI_TEST_S3_SECRET_KEY"), "path")
	if err != nil {
		t.Fatal(err)
	}
	runAvatarStorageRoundTrip(t, files)
	runAvatarStorageFailureCleanup(t, files)
}

func runAvatarStorageRoundTrip(t *testing.T, files storage.Files) {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatal(err)
	}
	if err := db.AutoMigrate(&models.User{}); err != nil {
		t.Fatal(err)
	}
	previousDB, previousStore := database.DB, avatarFiles
	t.Cleanup(func() { database.DB, avatarFiles = previousDB, previousStore })
	database.DB = db
	avatarFiles = files
	user := models.User{Email: "avatar@example.test", Username: "avataruser", AccountStatus: "active"}
	if err := db.Create(&user).Error; err != nil {
		t.Fatal(err)
	}
	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.Use(func(c *gin.Context) { c.Set("user_email", user.Email); c.Next() })
	router.POST("/avatar", UploadAvatar)
	router.GET("/avatar/:username", GetPublicAvatar)
	router.DELETE("/avatar", DeleteAvatar)
	bitmap := image.NewRGBA(image.Rect(0, 0, 4, 4))
	for y := 0; y < 4; y++ {
		for x := 0; x < 4; x++ {
			bitmap.Set(x, y, color.RGBA{R: 200, A: 255})
		}
	}
	var file bytes.Buffer
	if err := png.Encode(&file, bitmap); err != nil {
		t.Fatal(err)
	}
	var body bytes.Buffer
	writer := multipart.NewWriter(&body)
	part, err := writer.CreateFormFile("avatar", "portrait.png")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := part.Write(file.Bytes()); err != nil {
		t.Fatal(err)
	}
	writer.Close()
	payload := append([]byte(nil), body.Bytes()...)
	unauthorized := gin.New()
	unauthorized.POST("/avatar", UploadAvatar)
	request := httptest.NewRequest(http.MethodPost, "/avatar", bytes.NewReader(payload))
	request.Header.Set("Content-Type", writer.FormDataContentType())
	response := httptest.NewRecorder()
	unauthorized.ServeHTTP(response, request)
	if response.Code != http.StatusUnauthorized {
		t.Fatalf("未登录者可上传头像：%d", response.Code)
	}
	request = httptest.NewRequest(http.MethodPost, "/avatar", bytes.NewReader(payload))
	request.Header.Set("Content-Type", writer.FormDataContentType())
	response = httptest.NewRecorder()
	router.ServeHTTP(response, request)
	if response.Code != 200 {
		t.Fatalf("上传头像：%d %s", response.Code, response.Body.String())
	}
	if err := db.First(&user, user.ID).Error; err != nil {
		t.Fatal(err)
	}
	if user.AvatarKey == nil || !strings.HasPrefix(*user.AvatarKey, "files/avatars/") {
		t.Fatalf("未使用稳定文件键：%v", user.AvatarKey)
	}
	firstKey := *user.AvatarKey
	request = httptest.NewRequest(http.MethodPost, "/avatar", bytes.NewReader(payload))
	request.Header.Set("Content-Type", writer.FormDataContentType())
	response = httptest.NewRecorder()
	router.ServeHTTP(response, request)
	if response.Code != 200 {
		t.Fatalf("替换头像：%d %s", response.Code, response.Body.String())
	}
	if err := db.First(&user, user.ID).Error; err != nil || user.AvatarKey == nil || *user.AvatarKey == firstKey {
		t.Fatalf("替换未生成新引用：%v", err)
	}
	if _, err := files.Get(context.Background(), firstKey); err == nil {
		t.Fatal("旧头像对象仍存在")
	}
	response = httptest.NewRecorder()
	router.ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/avatar/avataruser", nil))
	if response.Code != 200 || response.Header().Get("Content-Type") != "image/jpeg" || response.Body.Len() == 0 {
		t.Fatalf("读取头像：%d", response.Code)
	}
	response = httptest.NewRecorder()
	router.ServeHTTP(response, httptest.NewRequest(http.MethodDelete, "/avatar", nil))
	if response.Code != http.StatusNoContent {
		t.Fatalf("删除头像：%d", response.Code)
	}
	response = httptest.NewRecorder()
	router.ServeHTTP(response, httptest.NewRequest(http.MethodGet, "/avatar/avataruser", nil))
	if response.Code != 404 {
		t.Fatalf("删除后仍可读取：%d", response.Code)
	}
}

type recordingAvatarFiles struct {
	storage.Files
	lastKey string
}

func (f *recordingAvatarFiles) Put(ctx context.Context, key string, data []byte, mediaType string) error {
	f.lastKey = key
	return f.Files.Put(ctx, key, data, mediaType)
}

func runAvatarStorageFailureCleanup(t *testing.T, files storage.Files) {
	db, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	if err != nil {
		t.Fatal(err)
	}
	if err := db.AutoMigrate(&models.User{}); err != nil {
		t.Fatal(err)
	}
	previousDB, previousStore := database.DB, avatarFiles
	t.Cleanup(func() { database.DB, avatarFiles = previousDB, previousStore })
	database.DB = db
	recording := &recordingAvatarFiles{Files: files}
	avatarFiles = recording
	user := models.User{Email: "failure@example.test", Username: "avatarfailure", AccountStatus: "active"}
	if err := db.Create(&user).Error; err != nil {
		t.Fatal(err)
	}
	if err := db.Callback().Update().Before("gorm:update").Register("fail_avatar_update", func(tx *gorm.DB) {
		tx.AddError(errors.New("isolated database failure"))
	}); err != nil {
		t.Fatal(err)
	}
	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.Use(func(c *gin.Context) { c.Set("user_email", user.Email); c.Next() })
	router.POST("/avatar", UploadAvatar)
	bitmap := image.NewRGBA(image.Rect(0, 0, 4, 4))
	var imageData bytes.Buffer
	if err := png.Encode(&imageData, bitmap); err != nil {
		t.Fatal(err)
	}
	var body bytes.Buffer
	writer := multipart.NewWriter(&body)
	part, err := writer.CreateFormFile("avatar", "portrait.png")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := part.Write(imageData.Bytes()); err != nil {
		t.Fatal(err)
	}
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}
	request := httptest.NewRequest(http.MethodPost, "/avatar", &body)
	request.Header.Set("Content-Type", writer.FormDataContentType())
	response := httptest.NewRecorder()
	router.ServeHTTP(response, request)
	if response.Code != http.StatusInternalServerError || recording.lastKey == "" {
		t.Fatalf("数据库失败后未按预期清理新头像：%d", response.Code)
	}
	if _, err := files.Get(context.Background(), recording.lastKey); err == nil {
		t.Fatal("数据库失败后新头像对象仍存在")
	}
}
