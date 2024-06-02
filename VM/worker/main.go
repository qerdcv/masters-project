/*
	This program is used to run on the virtual machine part as Daemon.
	It expects that user has been authenticated with Gmail OAuth, and already has email.
	All data that need this program is passed via Environment variables.
*/

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

// init method is used to initialize all program variables from the environment variables
func init() {
	userEmail = os.Getenv("USER_EMAIL")
	ltiHost = os.Getenv("LTI_HOST")
	testsDir = os.Getenv("TESTS_DIR")
	env = os.Getenv("ENV")
}

// logErr is just an alias for log.Println with "ERROR:" prefix
func logErr(msg string) {
	log.Println("ERROR:", msg)
}

// fatal is used to log error and exit with code 1 (error)
func fatal(msg string) {
	logErr(msg)
	os.Exit(1)
}

// taskRequest is representing structure that is passed from backend to the VM via websocket
type testRequest struct {
	TaskID string `json:"task_id"` // Task identifier (from the LTI)
	Test   string `json:"test"`    // Test name (also from the LTI)
}

// processMessage is used to handle messages that comes from WebSockets
// ctx - is application`s context. context.Done means that application is being shut down, and processing needs to be stopped
// c - is a websocket connection to the python backend
func processMessages(ctx context.Context, c *websocket.Conn) {
	for {
		select {
		case <-ctx.Done():
			return
		default:
			// read message from the websocket connection
			// on error - just log it and exit from the goroutine
			// TODO: use errgroup to handle error
			// maybe connection needs to be recreated
			_, message, err := c.ReadMessage()
			if err != nil {
				logErr(err.Error())
				return
			}

			// unmarshal bytes that received from the messages into testRequest structure
			var test testRequest
			if err = json.Unmarshal(message, &test); err != nil {
				logErr(err.Error())
				continue
			}

			// if test has no task id - wait for another message
			// TODO: log an error here, that's unexpected behavior
			if test.TaskID == "" {
				continue
			}

			result, err := runTest(test.TaskID, test.Test)
			if err != nil {
				logErr(err.Error())
				continue
			}

			// marshal test result into bytes
			b, err := json.Marshal(result)
			if err != nil {
				logErr(err.Error())
				continue
			}

			// send execution result back to the backend
			if err = c.WriteMessage(websocket.TextMessage, b); err != nil {
				logErr(err.Error())
				continue
			}
		}
	}
}

// testResult is representing the result for the specific test
type testResult struct {
	Name   string `json:"name"`
	Result struct {
		Status string `json:"status"`
		Error  string `json:"error,omitempty"`
	} `json:"result"`
}

func runTest(taskID string, test string) (testResult, error) {
	// choosing schema (for the local env - you mostly prefer to use http over https)
	scheme := "http"
	if env == "prod" {
		scheme = "https"
	}

	// build url for the test`s executable file that needs to be downloaded
	u := url.URL{Scheme: scheme, Host: ltiHost, Path: "/tests/download/" + taskID + "/" + test}
	resp, err := http.Get(u.String())
	if err != nil {
		return testResult{}, fmt.Errorf("http get: %w", err)
	}

	defer resp.Body.Close()

	// create path to the executable file that is gonna to be downloaded
	testPath := path.Join(testsDir, fmt.Sprintf("%s_%s", test, taskID))
	f, err := os.Create(testPath)
	if err != nil {
		return testResult{}, fmt.Errorf("create test: %w", err)
	}

	// executable file downloading
	if _, err = io.Copy(f, resp.Body); err != nil {
		return testResult{}, fmt.Errorf("write test: %w", err)
	}

	if err = f.Close(); err != nil {
		return testResult{}, fmt.Errorf("close file: %w", err)
	}

	// after test run - delete the executable file, since it is not longer needed
	// TODO: probably good solution will be keep this files in the /tmp folder, to not download tests on every run
	// and keep it cached
	defer os.Remove(testPath)

	// change the mod of the file, that allows to execute it
	if err = os.Chmod(testPath, fs.ModePerm); err != nil {
		return testResult{}, fmt.Errorf("change test mode: %w", err)
	}

	result := testResult{
		Name: test,
	}

	// execute downloaded executable
	if out, execErr := exec.Command(testPath).CombinedOutput(); execErr != nil {
		// if there is an error - mark test as failed, and put the output of the program as the error message
		result.Result.Status = "failed"
		result.Result.Error = fmt.Sprintf("%s: %s", string(out), execErr.Error())
		return result, nil
	}

	// if there is no errors - mark test as success
	result.Result.Status = "success"
	return result, nil
}

func main() {
	// determine schema based from the env
	// for local environment we are using not save version (ws) of schema
	scheme := "ws"
	if env == "prod" {
		scheme = "wss"
	}

	// building an url for the websocket connection
	u := url.URL{Scheme: scheme, Host: ltiHost, Path: "/ws/server/" + userEmail}
	// connecting to the websocket
	c, _, err := websocket.DefaultDialer.Dial(u.String(), nil)
	if err != nil {
		// if we are failed to connect - log error and exit
		fatal(err.Error())
		return
	}

	ctx, cancel := context.WithCancel(context.Background())
	interrupt := make(chan os.Signal, 1)
	signal.Notify(interrupt, os.Interrupt, syscall.SIGINT, syscall.SIGTERM)

	// running background process (goroutine) that processes messages from the websocket connection
	go processMessages(ctx, c)
	// running background goroutine that pings the connection to the backend`s websocket
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

	// graceful shutdown
	// send close event to the backend
	// and close the connection
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
