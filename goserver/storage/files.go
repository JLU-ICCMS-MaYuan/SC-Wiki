// Package storage 为账号接口提供统一的私有文件操作。
package storage

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/credentials"
	"github.com/aws/aws-sdk-go-v2/service/s3"
	"github.com/aws/smithy-go"
)

var ErrConflict = errors.New("文件键已被不同内容占用")
var ErrUnavailable = errors.New("文件存储暂时不可用")
var ErrInvalidKey = errors.New("文件键无效")

type Files interface {
	Put(ctx context.Context, key string, content []byte, mediaType string) error
	Get(ctx context.Context, key string) ([]byte, error)
	Delete(ctx context.Context, key string) error
}

func validKey(key string) bool {
	if key == "" || len(key) > 500 || strings.ContainsAny(key, "\\\r\n\x00") {
		return false
	}
	for _, part := range strings.Split(key, "/") {
		if part == "" || part == "." || part == ".." {
			return false
		}
	}
	return true
}

type localFiles struct{ root string }

func NewLocal(root string) Files { return &localFiles{root: root} }

func (f *localFiles) path(key string) (string, error) {
	if !validKey(key) {
		return "", ErrInvalidKey
	}
	root, err := filepath.Abs(f.root)
	if err != nil {
		return "", ErrUnavailable
	}
	path := filepath.Join(root, filepath.FromSlash(key))
	current := root
	for _, part := range strings.Split(key, "/") {
		current = filepath.Join(current, part)
		info, err := os.Lstat(current)
		if err == nil && info.Mode()&os.ModeSymlink != 0 {
			return "", ErrInvalidKey
		}
		if err != nil && !os.IsNotExist(err) {
			return "", ErrUnavailable
		}
	}
	return path, nil
}

func (f *localFiles) Put(_ context.Context, key string, content []byte, _ string) error {
	path, err := f.path(key)
	if err != nil {
		return err
	}
	if err = os.MkdirAll(filepath.Dir(path), 0o750); err != nil {
		return ErrUnavailable
	}
	tmp, err := os.CreateTemp(filepath.Dir(path), ".upload-")
	if err != nil {
		return ErrUnavailable
	}
	defer os.Remove(tmp.Name())
	if _, err = tmp.Write(content); err != nil {
		tmp.Close()
		return ErrUnavailable
	}
	if err = tmp.Close(); err != nil {
		return ErrUnavailable
	}
	if err = os.Link(tmp.Name(), path); err == nil {
		return nil
	} else if !os.IsExist(err) {
		return ErrUnavailable
	}
	existing, err := os.ReadFile(path)
	if err != nil {
		return ErrUnavailable
	}
	if !bytes.Equal(existing, content) {
		return ErrConflict
	}
	return nil
}

func (f *localFiles) Get(_ context.Context, key string) ([]byte, error) {
	path, err := f.path(key)
	if err != nil {
		return nil, err
	}
	return os.ReadFile(path)
}

func (f *localFiles) Delete(_ context.Context, key string) error {
	path, err := f.path(key)
	if err != nil {
		return err
	}
	if err = os.Remove(path); err != nil && !os.IsNotExist(err) {
		return ErrUnavailable
	}
	return nil
}

type s3Files struct {
	client *s3.Client
	bucket string
}

func NewS3(endpoint, region, bucket, accessKey, secretKey, addressingStyle string) (Files, error) {
	if endpoint == "" || bucket == "" || accessKey == "" || secretKey == "" {
		return nil, errors.New("S3 存储配置不完整")
	}
	if region == "" {
		region = "us-east-1"
	}
	if addressingStyle == "" {
		addressingStyle = "path"
	}
	if addressingStyle != "path" && addressingStyle != "virtual" {
		return nil, errors.New("S3 寻址方式无效")
	}
	cfg := aws.Config{
		Region: region, Credentials: credentials.NewStaticCredentialsProvider(accessKey, secretKey, ""),
		HTTPClient: &http.Client{Timeout: 60 * time.Second}, RetryMaxAttempts: 3,
	}
	client := s3.NewFromConfig(cfg, func(o *s3.Options) {
		o.BaseEndpoint = aws.String(endpoint)
		o.UsePathStyle = addressingStyle == "path"
	})
	return &s3Files{client: client, bucket: bucket}, nil
}

func (f *s3Files) Put(ctx context.Context, key string, content []byte, mediaType string) error {
	if !validKey(key) {
		return ErrInvalidKey
	}
	sum := sha256.Sum256(content)
	_, err := f.client.PutObject(ctx, &s3.PutObjectInput{
		Bucket: aws.String(f.bucket), Key: aws.String(key), Body: bytes.NewReader(content),
		ContentType: aws.String(mediaType), ContentLength: aws.Int64(int64(len(content))),
		Metadata: map[string]string{"sha256": hex.EncodeToString(sum[:])}, IfNoneMatch: aws.String("*"),
	})
	if err == nil {
		return nil
	}
	var apiErr smithy.APIError
	if errors.As(err, &apiErr) && (apiErr.ErrorCode() == "PreconditionFailed" || apiErr.ErrorCode() == "ConditionalRequestConflict") {
		old, readErr := f.Get(ctx, key)
		if readErr != nil {
			return readErr
		}
		if bytes.Equal(old, content) {
			return nil
		}
		return ErrConflict
	}
	return ErrUnavailable
}

func (f *s3Files) Get(ctx context.Context, key string) ([]byte, error) {
	if !validKey(key) {
		return nil, ErrInvalidKey
	}
	result, err := f.client.GetObject(ctx, &s3.GetObjectInput{Bucket: aws.String(f.bucket), Key: aws.String(key)})
	if err != nil {
		var apiErr smithy.APIError
		if errors.As(err, &apiErr) && (apiErr.ErrorCode() == "NoSuchKey" || apiErr.ErrorCode() == "404") {
			return nil, os.ErrNotExist
		}
		return nil, ErrUnavailable
	}
	defer result.Body.Close()
	content, err := io.ReadAll(io.LimitReader(result.Body, 2*1024*1024+1))
	if err != nil || len(content) > 2*1024*1024 {
		return nil, ErrUnavailable
	}
	expected := result.Metadata["sha256"]
	if expected == "" {
		return nil, ErrConflict
	}
	sum := sha256.Sum256(content)
	if hex.EncodeToString(sum[:]) != expected {
		return nil, ErrConflict
	}
	return content, nil
}

func (f *s3Files) Delete(ctx context.Context, key string) error {
	if !validKey(key) {
		return ErrInvalidKey
	}
	if _, err := f.client.DeleteObject(ctx, &s3.DeleteObjectInput{Bucket: aws.String(f.bucket), Key: aws.String(key)}); err != nil {
		return ErrUnavailable
	}
	return nil
}
