package services

import (
	"crypto/tls"
	"fmt"
	"mime"
	"net"
	"net/mail"
	"net/smtp"
	"strings"
	"time"
)

type EmailConfig struct {
	Host, Port, Username, Password, From, TLSMode string
}

type Mailer interface {
	SendVerificationCode(to, code string) error
}

type SMTPMailer struct {
	config EmailConfig
	// 仅供同包测试使用，生产始终验证服务器证书。
	tlsConfig *tls.Config
	timeout   time.Duration
}

func NewSMTPMailer(config EmailConfig) *SMTPMailer {
	return &SMTPMailer{config: config, timeout: 20 * time.Second}
}

func mailbox(address string) bool {
	parsed, err := mail.ParseAddress(address)
	return err == nil && parsed.Address == address && !strings.ContainsAny(address, "\r\n")
}

func (m *SMTPMailer) Configured() bool {
	mode := strings.ToLower(m.config.TLSMode)
	return m.config.Host != "" && m.config.Port != "" && mailbox(m.config.From) &&
		m.config.Username != "" && m.config.Password != "" && (mode == "implicit" || mode == "starttls")
}

func (m *SMTPMailer) SendVerificationCode(to, code string) error {
	if !m.Configured() {
		return fmt.Errorf("SMTP 配置不完整或 TLS 模式无效")
	}
	if !mailbox(to) || len(code) != 6 || strings.IndexFunc(code, func(r rune) bool { return r < '0' || r > '9' }) >= 0 {
		return fmt.Errorf("收件地址或验证码格式错误")
	}
	deadline := time.Now().Add(m.timeout)
	conn, err := net.DialTimeout("tcp", net.JoinHostPort(m.config.Host, m.config.Port), m.timeout)
	if err != nil {
		return err
	}
	defer conn.Close()
	if err := conn.SetDeadline(deadline); err != nil {
		return err
	}
	tlsConfig := m.tlsConfig
	if tlsConfig == nil {
		tlsConfig = &tls.Config{ServerName: m.config.Host, MinVersion: tls.VersionTLS12}
	}
	if strings.EqualFold(m.config.TLSMode, "implicit") {
		secure := tls.Client(conn, tlsConfig)
		if err := secure.Handshake(); err != nil {
			return err
		}
		conn = secure
	}
	client, err := smtp.NewClient(conn, m.config.Host)
	if err != nil {
		return err
	}
	defer client.Close()
	if strings.EqualFold(m.config.TLSMode, "starttls") {
		if ok, _ := client.Extension("STARTTLS"); !ok {
			return fmt.Errorf("SMTP 服务不支持 STARTTLS")
		}
		if err := client.StartTLS(tlsConfig); err != nil {
			return err
		}
	}
	if err := client.Auth(smtp.PlainAuth("", m.config.Username, m.config.Password, m.config.Host)); err != nil {
		return err
	}
	if err := client.Mail(m.config.From); err != nil {
		return err
	}
	if err := client.Rcpt(to); err != nil {
		return err
	}
	writer, err := client.Data()
	if err != nil {
		return err
	}
	message := "From: " + m.config.From + "\r\nTo: " + to +
		"\r\nSubject: " + mime.QEncoding.Encode("UTF-8", "SC-Wiki 邮箱验证码") +
		"\r\nMIME-Version: 1.0\r\nContent-Type: text/plain; charset=UTF-8\r\nContent-Transfer-Encoding: 8bit\r\n\r\n" +
		fmt.Sprintf("您的 SC-Wiki 验证码是：%s\r\n验证码 5 分钟内有效，请勿转发。\r\n如果您没有申请注册，请忽略此邮件。\r\n", code)
	if _, err := writer.Write([]byte(message)); err != nil {
		return err
	}
	// DATA 的成功响应已表示服务器接受邮件；QUIT 失败不能把已接受的邮件算作失败。
	if err := writer.Close(); err != nil {
		return err
	}
	_ = client.Quit()
	return nil
}
