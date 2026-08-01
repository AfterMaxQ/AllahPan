package com.allahpan.component;

import com.allahpan.common.log.LogContext;
import com.allahpan.common.log.StructuredLog;
import jakarta.mail.*;
import jakarta.mail.internet.*;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.util.Properties;

/**
 * 邮件发送服务 — 通过 QQ 邮箱 SMTP 发送验证码
 */
@Component
public class MailService {

    private static final Logger LOG = LoggerFactory.getLogger(MailService.class);

    @Value("${mail.host}")
    private String host;
    @Value("${mail.port}")
    private int port;
    @Value("${mail.username}")
    private String username;
    @Value("${mail.password}")
    private String password;
    @Value("${mail.from}")
    private String from;

    /**
     * 发送 HTML 验证码邮件（暖木色主题）
     * @param toEmail 收件人邮箱
     * @param code    6 位验证码
     */
    public void send(String toEmail, String code) {
        try {
            Properties props = new Properties();
            props.put("mail.smtp.auth", "true");
            props.put("mail.smtp.starttls.enable", "true");
            props.put("mail.smtp.host", host);
            props.put("mail.smtp.port", String.valueOf(port));

            Session session = Session.getInstance(props, new Authenticator() {
                @Override
                protected PasswordAuthentication getPasswordAuthentication() {
                    return new PasswordAuthentication(username, password);
                }
            });

            Message msg = new MimeMessage(session);
            msg.setFrom(new InternetAddress(from));
            msg.setRecipient(Message.RecipientType.TO, new InternetAddress(toEmail));
            msg.setSubject("AllahPan 登录验证码");

            String html = """
                <div style="max-width:480px;margin:0 auto;font-family:'PingFang SC','Microsoft YaHei',sans-serif">
                  <div style="background:linear-gradient(135deg,#C4946B,#D5B193);padding:40px 24px 32px;text-align:center;border-radius:16px 16px 0 0">
                    <div style="font-size:36px;margin-bottom:8px">&#127968;</div>
                    <h1 style="color:#fff;font-size:22px;font-weight:600;margin:0">AllahPan</h1>
                    <p style="color:rgba(255,255,255,0.85);font-size:14px;margin:6px 0 0">家庭共享云盘</p>
                  </div>
                  <div style="background:#fff;padding:32px 24px;border:1px solid #E8E0D5;border-top:none;border-radius:0 0 16px 16px">
                    <p style="color:#3D3226;font-size:15px;margin:0 0 8px;text-align:center">您的登录验证码</p>
                    <div style="background:#FAF7F2;border:2px dashed #E8E0D5;border-radius:12px;padding:20px;text-align:center;margin:16px 0">
                      <span style="font-size:36px;font-weight:700;color:#C4946B;letter-spacing:8px;font-family:'SF Mono','JetBrains Mono',monospace">%s</span>
                    </div>
                    <p style="color:#8B7E6E;font-size:12px;text-align:center;margin:0">验证码 5 分钟内有效，请勿转发给他人</p>
                    <hr style="border:none;border-top:1px solid #E8E0D5;margin:24px 0 0" />
                    <p style="color:#BFB5A8;font-size:11px;text-align:center;margin:12px 0 0">AllahPan &mdash; 安全存留每一份家庭记忆</p>
                  </div>
                </div>
                """.formatted(code);

            msg.setContent(html, "text/html; charset=utf-8");
            Transport.send(msg);
            LOG.info(StructuredLog.event("auth.code.sent", "recipient", LogContext.maskEmail(toEmail)));
        } catch (MessagingException e) {
            LOG.error(StructuredLog.event("auth.code.send_failed", "recipient", LogContext.maskEmail(toEmail),
                    "errorType", e.getClass().getSimpleName()), e);
            throw new RuntimeException("邮件发送失败，请稍后重试", e);
        }
    }
}
