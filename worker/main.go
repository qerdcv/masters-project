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
	"syscall"
	"time"

	"github.com/gorilla/websocket"
)

func logErr(msg string) {
	log.Println("ERROR:", msg)
}

func fatal(msg string) {
	logErr(msg)
	os.Exit(1)
}

type wsMessage struct {
	Command string   `json:"command"`
	Args    []string `json:"args"`
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

			var tests []string
			if err = json.Unmarshal(message, &tests); err != nil {
				logErr(err.Error())
				continue
			}

			results, err := runTests(tests)
			if err != nil {
				logErr(err.Error())
				continue
			}

			b, err := json.Marshal(results)
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

func runTests(tests []string) ([]testResult, error) {
	results := make([]testResult, len(tests))
	for idx, test := range tests {
		result, err := runTest(test)
		if err != nil {
			return nil, fmt.Errorf("run test %s: %w", test, err)
		}

		results[idx] = result
	}

	return results, nil
}

func runTest(test string) (testResult, error) {
	downloadDir := "/home/qerdcv/own_projects/python/masters-project/worker/"
	resp, err := http.Get("http://192.168.31.57:9001/tests/download/" + test)
	if err != nil {
		return testResult{}, fmt.Errorf("http get: %w", err)
	}

	defer resp.Body.Close()

	f, err := os.Create(downloadDir + test)
	if err != nil {
		return testResult{}, fmt.Errorf("create test: %w", err)
	}

	if _, err = io.Copy(f, resp.Body); err != nil {
		return testResult{}, fmt.Errorf("write test: %w", err)
	}

	if err = f.Close(); err != nil {
		return testResult{}, fmt.Errorf("close file: %w", err)
	}

	defer os.Remove(test)

	if err = os.Chmod(downloadDir+test, fs.ModePerm); err != nil {
		return testResult{}, fmt.Errorf("change test mode: %w", err)
	}

	result := testResult{
		Name: test,
	}

	if err = exec.Command(downloadDir + test).Run(); err != nil {
		result.Result.Status = "failed"
		result.Result.Error = err.Error()
		return result, nil
	}

	result.Result.Status = "success"
	return result, nil
}

func main() {
	u := url.URL{Scheme: "ws", Host: "192.168.31.57:9001", Path: "/ws/server/rikepic@gmail.com"}
	c, resp, err := websocket.DefaultDialer.Dial(u.String(), nil)
	if err != nil {
		fatal(err.Error() + resp.Status)
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
