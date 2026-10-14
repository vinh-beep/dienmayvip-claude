package main

// IMAP tối giản cho Gmail (imap.gmail.com:993, mật khẩu ứng dụng Google):
// tìm thư từ einvoice@fastsoftware.com.vn, tải nội dung, đọc link Fast e-Invoice.

import (
	"bufio"
	"crypto/tls"
	"encoding/base64"
	"errors"
	"fmt"
	"io"
	"mime"
	"mime/multipart"
	"mime/quotedprintable"
	"net"
	"net/mail"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"time"
)

type imapKet struct {
	c   net.Conn
	r   *bufio.Reader
	tag int
}

func imapKetNoi(diaChi, user, matKhau string) (*imapKet, error) {
	d := &net.Dialer{Timeout: 20 * time.Second}
	c, err := tls.DialWithDialer(d, "tcp", diaChi, &tls.Config{ServerName: strings.Split(diaChi, ":")[0]})
	if err != nil {
		return nil, err
	}
	k := &imapKet{c: c, r: bufio.NewReaderSize(c, 1<<20)}
	c.SetDeadline(time.Now().Add(120 * time.Second))
	if _, err := k.r.ReadString('\n'); err != nil { // lời chào
		return nil, err
	}
	if _, err := k.lenh(fmt.Sprintf("LOGIN %s %s", imapQuote(user), imapQuote(matKhau))); err != nil {
		return nil, errors.New("đăng nhập IMAP thất bại (cần bật IMAP trong Gmail và dùng Mật khẩu ứng dụng): " + err.Error())
	}
	return k, nil
}

func imapQuote(s string) string {
	return `"` + strings.NewReplacer(`\`, `\\`, `"`, `\"`).Replace(s) + `"`
}

// lenh gửi 1 lệnh, trả về toàn bộ dòng phản hồi (xử lý literal {n}).
func (k *imapKet) lenh(cmd string) ([]string, error) {
	k.tag++
	tag := fmt.Sprintf("A%03d", k.tag)
	k.c.SetDeadline(time.Now().Add(120 * time.Second))
	if _, err := fmt.Fprintf(k.c, "%s %s\r\n", tag, cmd); err != nil {
		return nil, err
	}
	var dong []string
	for {
		l, err := k.r.ReadString('\n')
		if err != nil {
			return dong, err
		}
		l = strings.TrimRight(l, "\r\n")
		if i := strings.LastIndex(l, "{"); i >= 0 && strings.HasSuffix(l, "}") {
			if n, err := strconv.Atoi(l[i+1 : len(l)-1]); err == nil {
				buf := make([]byte, n)
				if _, err := io.ReadFull(k.r, buf); err != nil {
					return dong, err
				}
				l += "\n" + string(buf)
			}
		}
		dong = append(dong, l)
		if strings.HasPrefix(l, tag+" ") {
			if strings.HasPrefix(l, tag+" OK") {
				return dong, nil
			}
			return dong, errors.New(strings.TrimPrefix(l, tag+" "))
		}
	}
}

func (k *imapKet) dong() { k.lenh("LOGOUT"); k.c.Close() }

var reSearch = regexp.MustCompile(`^\* SEARCH(.*)$`)

// ThuHDDT = nội dung text + đính kèm (xml/pdf/zip) của một thư.
type ThuHDDT struct {
	Text    string
	DinhKem []DinhKem
}
type DinhKem struct {
	Ten string
	Du  []byte
}

// TimEmailHDDTIMAP lấy thư HĐĐT từ các địa chỉ gửi (cách nhau dấu phẩy) kể từ tuNgay (dd/mm/yyyy).
func TimEmailHDDTIMAP(user, matKhau, nguoiGui, tuNgay string, toiDa int) ([]ThuHDDT, error) {
	k, err := imapKetNoi("imap.gmail.com:993", user, matKhau)
	if err != nil {
		return nil, err
	}
	defer k.dong()
	hop := `"[Gmail]/All Mail"`
	if _, err := k.lenh("EXAMINE " + hop); err != nil {
		hop = "INBOX"
		if _, err := k.lenh("EXAMINE " + hop); err != nil {
			return nil, err
		}
	}
	since := ""
	if t, err := time.Parse("02/01/2006", tuNgay); err == nil {
		since = " SINCE " + t.Format("02-Jan-2006")
	}
	var ids []string
	gui := tachDS(nguoiGui)
	if len(gui) == 0 {
		gui = []string{"einvoice@fastsoftware.com.vn"}
	}
	for _, g := range gui {
		dong, err := k.lenh(`SEARCH FROM "` + g + `"` + since)
		if err != nil {
			return nil, err
		}
		for _, l := range dong {
			if m := reSearch.FindStringSubmatch(l); m != nil {
				ids = append(ids, strings.Fields(m[1])...)
			}
		}
	}
	if len(ids) > toiDa {
		ids = ids[len(ids)-toiDa:]
	}
	var ket []ThuHDDT
	for _, id := range ids {
		dong, err := k.lenh("FETCH " + id + " (BODY.PEEK[])")
		if err != nil {
			continue
		}
		raw := strings.Join(dong, "\n")
		if i := strings.Index(raw, "\n"); i >= 0 {
			raw = raw[i+1:]
		}
		th := DocThu(raw)
		if th.Text != "" || len(th.DinhKem) > 0 {
			ket = append(ket, th)
		}
	}
	return ket, nil
}

// DocThu đọc thư MIME thô: text + đính kèm xml/pdf/zip.
func DocThu(raw string) ThuHDDT {
	th := ThuHDDT{}
	msg, err := mail.ReadMessage(strings.NewReader(raw))
	if err != nil {
		th.Text = giaiMaPhan(raw, "", "")
		return th
	}
	body, _ := io.ReadAll(msg.Body)
	th.Text = docPhanMIME2(string(body), msg.Header.Get("Content-Type"), msg.Header.Get("Content-Transfer-Encoding"), msg.Header.Get("Content-Disposition"), &th.DinhKem)
	return th
}

func docPhanMIME2(body, ct, cte, cd string, dk *[]DinhKem) string {
	mt, params, _ := mime.ParseMediaType(ct)
	if strings.HasPrefix(mt, "multipart/") && params["boundary"] != "" {
		mr := multipart.NewReader(strings.NewReader(body), params["boundary"])
		plain, html := "", ""
		for {
			p, err := mr.NextPart()
			if err != nil {
				break
			}
			b, _ := io.ReadAll(p)
			t := docPhanMIME2(string(b), p.Header.Get("Content-Type"), p.Header.Get("Content-Transfer-Encoding"), p.Header.Get("Content-Disposition"), dk)
			pct, _, _ := mime.ParseMediaType(p.Header.Get("Content-Type"))
			if pct == "text/plain" && plain == "" {
				plain = t
			} else if t != "" && html == "" && !strings.HasPrefix(pct, "application/") {
				html = t
			}
		}
		if plain != "" {
			return plain
		}
		return html
	}
	ten := tenDinhKem(ct, cd)
	if ten != "" {
		duoi := strings.ToLower(filepath.Ext(ten))
		if duoi == ".xml" || duoi == ".pdf" || duoi == ".zip" {
			var du []byte
			switch strings.ToLower(strings.TrimSpace(cte)) {
			case "base64":
				du, _ = base64.StdEncoding.DecodeString(strings.Join(strings.Fields(body), ""))
			case "quoted-printable":
				du, _ = io.ReadAll(quotedprintable.NewReader(strings.NewReader(body)))
			default:
				du = []byte(body)
			}
			if len(du) > 0 {
				*dk = append(*dk, DinhKem{Ten: filepath.Base(ten), Du: du})
			}
			return ""
		}
	}
	return giaiMaPhan(body, mt, cte)
}

var dec = new(mime.WordDecoder)

func tenDinhKem(ct, cd string) string {
	if _, p, err := mime.ParseMediaType(cd); err == nil && p["filename"] != "" {
		if t, err := dec.DecodeHeader(p["filename"]); err == nil {
			return t
		}
		return p["filename"]
	}
	if _, p, err := mime.ParseMediaType(ct); err == nil && p["name"] != "" {
		if t, err := dec.DecodeHeader(p["name"]); err == nil {
			return t
		}
		return p["name"]
	}
	return ""
}

// DocNoiDungMail rút text (ưu tiên text/plain, không thì HTML bỏ thẻ) từ thư MIME thô.
func DocNoiDungMail(raw string) string {
	msg, err := mail.ReadMessage(strings.NewReader(raw))
	if err != nil {
		return giaiMaPhan(raw, "", "")
	}
	ct := msg.Header.Get("Content-Type")
	cte := msg.Header.Get("Content-Transfer-Encoding")
	body, _ := io.ReadAll(msg.Body)
	return docPhanMIME(string(body), ct, cte)
}

func docPhanMIME(body, ct, cte string) string {
	mt, params, _ := mime.ParseMediaType(ct)
	if strings.HasPrefix(mt, "multipart/") && params["boundary"] != "" {
		mr := multipart.NewReader(strings.NewReader(body), params["boundary"])
		plain, html := "", ""
		for {
			p, err := mr.NextPart()
			if err != nil {
				break
			}
			b, _ := io.ReadAll(p)
			t := docPhanMIME(string(b), p.Header.Get("Content-Type"), p.Header.Get("Content-Transfer-Encoding"))
			pct, _, _ := mime.ParseMediaType(p.Header.Get("Content-Type"))
			if pct == "text/plain" && plain == "" {
				plain = t
			} else if t != "" && html == "" {
				html = t
			}
		}
		if plain != "" {
			return plain
		}
		return html
	}
	return giaiMaPhan(body, mt, cte)
}

var reThe = regexp.MustCompile(`(?s)<[^>]+>`)
var reHref = regexp.MustCompile(`(?is)<a[^>]*href="([^"]+)"[^>]*>`)

func giaiMaPhan(body, mt, cte string) string {
	switch strings.ToLower(strings.TrimSpace(cte)) {
	case "base64":
		if b, err := base64.StdEncoding.DecodeString(strings.Join(strings.Fields(body), "")); err == nil {
			body = string(b)
		}
	case "quoted-printable":
		if b, err := io.ReadAll(quotedprintable.NewReader(strings.NewReader(body))); err == nil {
			body = string(b)
		}
	}
	if strings.HasPrefix(mt, "text/html") || (mt == "" && strings.Contains(body, "<html")) {
		// giữ link trong href rồi bỏ thẻ
		body = reHref.ReplaceAllString(body, ` $1 `)
		body = reThe.ReplaceAllString(body, " ")
		body = strings.NewReplacer("&amp;", "&", "&nbsp;", " ", "&lt;", "<", "&gt;", ">").Replace(body)
	}
	return body
}
