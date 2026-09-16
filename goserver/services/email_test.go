package services

import (
	"bufio"
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"io"
	"mime"
	"net"
	"net/http/httptest"
	"net/mail"
	"net/textproto"
	"strings"
	"testing"
	"time"
)

// 本地真实 TLS/SMTP 服务，验证生产发送器的协议、认证与消息内容。
func smtpFixture(t *testing.T, mode, failure string) (*SMTPMailer, <-chan string) {
	t.Helper()
	certServer := httptest.NewTLSServer(nil)
	cert := certServer.TLS.Certificates[0]
	pool := x509.NewCertPool()
	pool.AddCert(certServer.Certificate())
	certServer.Close()
	tlsCfg := &tls.Config{Certificates: []tls.Certificate{cert}, MinVersion: tls.VersionTLS12}
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { listener.Close() })
	messages := make(chan string, 1)
	go func() {
		raw, err := listener.Accept()
		if err != nil {
			return
		}
		defer raw.Close()
		raw.SetDeadline(time.Now().Add(3 * time.Second))
		if failure == "timeout" {
			io.Copy(io.Discard, raw)
			return
		}
		var conn net.Conn = raw
		if mode == "implicit" {
			conn = tls.Server(raw, tlsCfg)
		}
		reader := bufio.NewReader(conn)
		fmt.Fprint(conn, "220 test SMTP\r\n")
		for {
			line, err := reader.ReadString('\n')
			if err != nil {
				return
			}
			switch {
			case strings.HasPrefix(line, "EHLO"):
				if mode == "starttls" && failure != "no-starttls" {
					fmt.Fprint(conn, "250-test\r\n250-STARTTLS\r\n250 AUTH PLAIN\r\n")
				} else {
					fmt.Fprint(conn, "250-test\r\n250 AUTH PLAIN\r\n")
				}
			case strings.HasPrefix(line, "STARTTLS"):
				fmt.Fprint(conn, "220 Ready\r\n")
				conn = tls.Server(raw, tlsCfg)
				reader = bufio.NewReader(conn)
			case strings.HasPrefix(line, "AUTH"):
				if failure == "auth" {
					fmt.Fprint(conn, "535 Denied\r\n")
				} else {
					fmt.Fprint(conn, "235 Authenticated\r\n")
				}
			case strings.HasPrefix(line, "MAIL"):
				if !strings.Contains(line, "sc_wiki@163.com") {
					t.Error("wrong sender")
				}
				fmt.Fprint(conn, "250 OK\r\n")
			case strings.HasPrefix(line, "RCPT"):
				if failure == "recipient" {
					fmt.Fprint(conn, "550 Denied\r\n")
				} else {
					fmt.Fprint(conn, "250 OK\r\n")
				}
			case strings.HasPrefix(line, "DATA"):
				fmt.Fprint(conn, "354 Send message\r\n")
				content, err := textproto.NewReader(reader).ReadDotBytes()
				if err != nil {
					return
				}
				if failure == "data" {
					fmt.Fprint(conn, "554 Rejected\r\n")
				} else {
					messages <- string(content)
					fmt.Fprint(conn, "250 Accepted\r\n")
				}
			case strings.HasPrefix(line, "QUIT"):
				fmt.Fprint(conn, "221 Bye\r\n")
				return
			default:
				fmt.Fprint(conn, "250 OK\r\n")
			}
		}
	}()
	host, port, _ := net.SplitHostPort(listener.Addr().String())
	sender := NewSMTPMailer(EmailConfig{Host: host, Port: port, Username: "sc_wiki@163.com", Password: "test-only", From: "sc_wiki@163.com", TLSMode: mode})
	sender.tlsConfig = &tls.Config{RootCAs: pool, ServerName: host, MinVersion: tls.VersionTLS12}
	return sender, messages
}

func TestSMTPVerificationDelivery(t *testing.T) {
	for _, mode := range []string{"implicit", "starttls"} {
		t.Run(mode, func(t *testing.T) {
			sender, messages := smtpFixture(t, mode, "")
			if err := sender.SendVerificationCode("recipient@example.test", "012345"); err != nil {
				t.Fatal(err)
			}
			select {
			case content := <-messages:
				msg, err := mail.ReadMessage(strings.NewReader(content))
				if err != nil {
					t.Fatal(err)
				}
				subject, err := new(mime.WordDecoder).DecodeHeader(msg.Header.Get("Subject"))
				if err != nil || subject != "SC-Wiki 邮箱验证码" {
					t.Fatalf("subject=%q err=%v", subject, err)
				}
				body, _ := io.ReadAll(msg.Body)
				if !strings.Contains(string(body), "012345") || msg.Header.Get("From") != "sc_wiki@163.com" {
					t.Fatal("incorrect mail content")
				}
			case <-time.After(time.Second):
				t.Fatal("message not delivered")
			}
		})
	}
}

func TestSMTPFailuresAndNoTLSFallback(t *testing.T) {
	for _, failure := range []string{"auth", "recipient", "data", "no-starttls", "timeout", "certificate"} {
		t.Run(failure, func(t *testing.T) {
			mode := "implicit"
			if failure == "no-starttls" {
				mode = "starttls"
			}
			sender, _ := smtpFixture(t, mode, failure)
			if failure == "timeout" {
				sender.timeout = 100 * time.Millisecond
			}
			if failure == "certificate" {
				sender.tlsConfig = nil
			}
			start := time.Now()
			if err := sender.SendVerificationCode("recipient@example.test", "012345"); err == nil {
				t.Fatal("failure reported success")
			}
			if failure == "timeout" && time.Since(start) > time.Second {
				t.Fatal("SMTP deadline ignored")
			}
		})
	}
}

func TestSMTPRejectsMissingConfigAndHeaderInjection(t *testing.T) {
	sender := NewSMTPMailer(EmailConfig{})
	if sender.Configured() || sender.SendVerificationCode("recipient@example.test", "123456") == nil {
		t.Fatal("missing config accepted")
	}
	sender = NewSMTPMailer(EmailConfig{Host: "localhost", Port: "465", Username: "user", Password: "secret", From: "sc_wiki@163.com", TLSMode: "implicit"})
	if sender.SendVerificationCode("a@example.test\r\nBcc: b@example.test", "123456") == nil {
		t.Fatal("header injection accepted")
	}
	if sender.SendVerificationCode("a@example.test", "12\r\n34") == nil {
		t.Fatal("code injection accepted")
	}
}
