package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"io/fs"
	"log"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"os/signal"
	"path"
	"syscall"
	"time"

	"github.com/gorilla/websocket"
)

var (
	userEmail,
	ltiHost,
	testsDir,
	env string
)

func init() {
	userEmail = os.Getenv("USER_EMAIL")
	ltiHost = os.Getenv("LTI_HOST")
	testsDir = os.Getenv("TESTS_DIR")
	env = os.Getenv("ENV")
}

func logErr(msg string) {
	log.Println("ERROR:", msg)
}

func fatal(msg string) {
	logErr(msg)
	os.Exit(1)
}

type testRequest struct {
	TaskID string `json:"task_id"`
	Test   string `json:"test"`
}

func proceedMessages(ctx context.Context, c *websocket.Conn) {
	for {
		select {
		case <-ctx.Done():
			return
		default:
			_, message, err := c.ReadMessage()
			if err != nil {
				logErr(err.Error())
				return
			}

			var test testRequest
			if err = json.Unmarshal(message, &test); err != nil {
				logErr(err.Error())
				continue
			}

			if test.TaskID == "" {
				continue
			}

			result, err := runTest(test.TaskID, test.Test)
			if err != nil {
				logErr(err.Error())
				continue
			}

			b, err := json.Marshal(result)
			if err != nil {
				logErr(err.Error())
				continue
			}

			if err = c.WriteMessage(websocket.TextMessage, b); err != nil {
				logErr(err.Error())
				continue
			}
		}
	}
}

type testResult struct {
	Name   string `json:"name"`
	Result struct {
		Status string `json:"status"`
		Error  string `json:"error,omitempty"`
	} `json:"result"`
}

func runTest(taskID string, test string) (testResult, error) {
	scheme := "http"
	if env == "prod" {
		scheme = "https"
	}

	u := url.URL{Scheme: scheme, Host: ltiHost, Path: "/tests/download/" + taskID + "/" + test}
	resp, err := http.Get(u.String())
	if err != nil {
		return testResult{}, fmt.Errorf("http get: %w", err)
	}

	defer resp.Body.Close()

	testPath := path.Join(testsDir, fmt.Sprintf("%s_%s", test, taskID))
	f, err := os.Create(testPath)
	if err != nil {
		return testResult{}, fmt.Errorf("create test: %w", err)
	}

	if _, err = io.Copy(f, resp.Body); err != nil {
		return testResult{}, fmt.Errorf("write test: %w", err)
	}

	if err = f.Close(); err != nil {
		return testResult{}, fmt.Errorf("close file: %w", err)
	}

	defer os.Remove(testPath)

	if err = os.Chmod(testPath, fs.ModePerm); err != nil {
		return testResult{}, fmt.Errorf("change test mode: %w", err)
	}

	result := testResult{
		Name: test,
	}

	if out, execErr := exec.Command(testPath).CombinedOutput(); execErr != nil {
		result.Result.Status = "failed"
		result.Result.Error = fmt.Sprintf("%s: %s", string(out), execErr.Error())
		return result, nil
	}

	result.Result.Status = "success"
	return result, nil
}

func main() {
	scheme := "ws"
	if env == "prod" {
		scheme = "wss"
	}

	u := url.URL{Scheme: scheme, Host: ltiHost, Path: "/ws/server/" + userEmail}
	c, _, err := websocket.DefaultDialer.Dial(u.String(), nil)
	if err != nil {
		fatal(err.Error())
	}

	ctx, cancel := context.WithCancel(context.Background())
	interrupt := make(chan os.Signal, 1)
	signal.Notify(interrupt, os.Interrupt, syscall.SIGINT, syscall.SIGTERM)

	go proceedMessages(ctx, c)
	go func(ctx context.Context) {
		t := time.NewTicker(5 * time.Second)
		defer t.Stop()

		for {
			select {
			case <-ctx.Done():
				return
			case <-t.C:
				if err = c.WriteMessage(websocket.PingMessage, nil); err != nil {
					logErr(err.Error())
					return
				}
			}
		}
	}(ctx)

	<-interrupt

	if err = c.WriteMessage(websocket.CloseMessage, websocket.FormatCloseMessage(websocket.CloseNormalClosure, "")); err != nil {
		log.Println("write close:", err)
		return
	}

	if err = c.Close(); err != nil {
		logErr("close connection")
	}

	cancel()
	log.Println("Exit..")
}
