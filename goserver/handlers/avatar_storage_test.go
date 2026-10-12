package handlers

import (
	"bytes"
	"image"
	"image/color"
	"image/png"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
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
	avatarFiles = storage.NewLocal(t.TempDir())
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
	request := httptest.NewRequest(http.MethodPost, "/avatar", &body)
	request.Header.Set("Content-Type", writer.FormDataContentType())
	response := httptest.NewRecorder()
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
