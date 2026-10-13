package storage

import (
	"bytes"
	"context"
	"errors"
	"os"
	"path/filepath"
	"testing"
)

func TestLocalFiles(t *testing.T) {
	root := t.TempDir()
	files := NewLocal(root)
	ctx := context.Background()
	key := "files/avatars/42/portrait.jpg"
	content := []byte("private avatar")
	if err := files.Put(ctx, key, content, "image/jpeg"); err != nil {
		t.Fatal(err)
	}
	if err := files.Put(ctx, key, content, "image/jpeg"); err != nil {
		t.Fatalf("相同内容应幂等：%v", err)
	}
	if err := files.Put(ctx, key, []byte("changed"), "image/jpeg"); !errors.Is(err, ErrConflict) {
		t.Fatalf("不同内容应冲突，得到 %v", err)
	}
	read, err := files.Get(ctx, key)
	if err != nil || !bytes.Equal(read, content) {
		t.Fatalf("读回内容错误：%v", err)
	}
	if err := files.Delete(ctx, key); err != nil {
		t.Fatal(err)
	}
	if err := files.Delete(ctx, key); err != nil {
		t.Fatalf("重复清理应幂等：%v", err)
	}
}

func TestLocalRejectsTraversalAndSymlink(t *testing.T) {
	root := t.TempDir()
	outside := t.TempDir()
	files := NewLocal(root)
	ctx := context.Background()
	for _, key := range []string{"/abs", "../escape", "a/../b", "a//b", "a\\b"} {
		if err := files.Put(ctx, key, []byte("x"), "text/plain"); !errors.Is(err, ErrInvalidKey) {
			t.Fatalf("%q: %v", key, err)
		}
	}
	if err := os.Symlink(outside, filepath.Join(root, "linked")); err != nil {
		t.Fatal(err)
	}
	if err := files.Put(ctx, "linked/secret", []byte("x"), "text/plain"); !errors.Is(err, ErrInvalidKey) {
		t.Fatalf("符号链接越界：%v", err)
	}
	if _, err := os.Stat(filepath.Join(outside, "secret")); !os.IsNotExist(err) {
		t.Fatalf("数据写入了根目录外：%v", err)
	}
}

func TestS3Protocol(t *testing.T) {
	endpoint := os.Getenv("SCWIKI_TEST_S3_ENDPOINT")
	if endpoint == "" {
		t.Skip("未配置隔离 S3 服务")
	}
	region := os.Getenv("SCWIKI_TEST_S3_REGION")
	if region == "" {
		region = "us-east-1"
	}
	access := os.Getenv("SCWIKI_TEST_S3_ACCESS_KEY")
	secret := os.Getenv("SCWIKI_TEST_S3_SECRET_KEY")
	if access == "" {
		access = "test"
	}
	if secret == "" {
		secret = "test"
	}
	files, err := NewS3(endpoint, region, "scwiki-storage-test", access, secret, "path")
	if err != nil {
		t.Fatal(err)
	}
	ctx := context.Background()
	key := "files/avatars/integration/go-avatar.jpg"
	defer files.Delete(ctx, key)
	content := []byte("go avatar bytes")
	if err := files.Put(ctx, key, content, "image/jpeg"); err != nil {
		t.Fatalf("S3 Put: %v", err)
	}
	read, err := files.Get(ctx, key)
	if err != nil || !bytes.Equal(read, content) {
		t.Fatalf("S3 Get: %v", err)
	}
	if err := files.Put(ctx, key, []byte("other"), "image/jpeg"); !errors.Is(err, ErrConflict) {
		t.Fatalf("S3 冲突处理：%v", err)
	}
}
