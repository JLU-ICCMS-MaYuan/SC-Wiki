package cache

import (
	"fmt"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
)

func TestVerificationAtomicLimitsAndConsumption(t *testing.T) {
	server := miniredis.RunT(t)
	Connect(server.Addr())
	now := time.Date(2026, 9, 16, 12, 0, 0, 0, time.UTC)
	var allowed atomic.Int32
	var wg sync.WaitGroup
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			retry, err := ReserveVerificationSend("email", "ip", now)
			if err != nil {
				t.Error(err)
			} else if retry == 0 {
				allowed.Add(1)
			}
		}()
	}
	wg.Wait()
	if allowed.Load() != 1 {
		t.Fatalf("concurrent sends=%d", allowed.Load())
	}
	if err := PublishVerificationCode("email", "digest", 5*time.Minute); err != nil {
		t.Fatal(err)
	}
	allowed.Store(0)
	for i := 0; i < 20; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			result, err := ConsumeVerificationCode("verify:code:email", "verify:attempts:email", "digest", 5, 5*time.Minute)
			if err != nil {
				t.Error(err)
			} else if result == "valid" {
				allowed.Add(1)
			}
		}()
	}
	wg.Wait()
	if allowed.Load() != 1 {
		t.Fatalf("concurrent validations=%d", allowed.Load())
	}
}

func TestVerificationExpiryReplacementAndFailedAttempts(t *testing.T) {
	server := miniredis.RunT(t)
	Connect(server.Addr())
	PublishVerificationCode("email", "old", 5*time.Minute)
	ConsumeVerificationCode("verify:code:email", "verify:attempts:email", "wrong", 5, 5*time.Minute)
	PublishVerificationCode("email", "new", 5*time.Minute)
	if server.Exists("verify:attempts:email") {
		t.Fatal("attempts not reset")
	}
	result, _ := ConsumeVerificationCode("verify:code:email", "verify:attempts:email", "old", 5, 5*time.Minute)
	if result != "invalid" {
		t.Fatal("old code accepted")
	}
	server.FastForward(5 * time.Minute)
	result, _ = ConsumeVerificationCode("verify:code:email", "verify:attempts:email", "new", 5, 5*time.Minute)
	if result != "missing" {
		t.Fatal("expired code accepted")
	}
}

func TestEmailAndIPHourlyDailyQuotas(t *testing.T) {
	for _, dimension := range []string{"email", "ip"} {
		t.Run(dimension, func(t *testing.T) {
			server := miniredis.RunT(t)
			Connect(server.Addr())
			now := time.Date(2026, 9, 16, 12, 0, 0, 0, time.UTC)
			for i := 0; i < 10; i++ {
				if i == 5 {
					server.FastForward(time.Hour)
					now = now.Add(time.Hour)
				}
				email, ip := "fixed-email", "fixed-ip"
				if dimension == "email" {
					ip = fmt.Sprint(i)
				} else {
					email = fmt.Sprint(i)
				}
				retry, err := ReserveVerificationSend(email, ip, now)
				if err != nil || retry != 0 {
					t.Fatalf("send %d retry=%d err=%v", i, retry, err)
				}
				server.FastForward(time.Minute)
				now = now.Add(time.Minute)
				if i == 4 {
					retry, err = ReserveVerificationSend("fixed-email", "fixed-ip", now)
					if err != nil || retry <= 0 {
						t.Fatalf("hour limit retry=%d err=%v", retry, err)
					}
				}
			}
			server.FastForward(time.Hour)
			now = now.Add(time.Hour)
			retry, err := ReserveVerificationSend("fixed-email", "fixed-ip", now)
			if err != nil || retry < 3600 {
				t.Fatalf("day limit retry=%d err=%v", retry, err)
			}
		})
	}
}
