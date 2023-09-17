package main

import (
	"context"
	"encoding/json"
	"log"
	"net/url"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gorilla/websocket"
)

func error(msg string) {
	log.Println("ERROR:", msg)
}

func fatal(msg string) {
	error(msg)
	os.Exit(1)
}

func proceedMessages(ctx context.Context, c *websocket.Conn) {
	for {
		select {
		case <-ctx.Done():
			return
		default:
			_, message, err := c.ReadMessage()
			if err != nil {
				error(err.Error())
				return
			}

			log.Println("recv: ", string(message))

		}
	}
}

func main() {
	u := url.URL{Scheme: "ws", Host: "localhost:8000", Path: "/ws/123"}
	c, resp, err := websocket.DefaultDialer.Dial(u.String(), nil)
	if err != nil {
		fatal(err.Error() + resp.Status)
	}

	defer c.Close()

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
				b, err := json.Marshal(map[string]string{
					"message": "hello",
				})
				if err != nil {
					error(err.Error())
					return
				}

				if err := c.WriteMessage(websocket.TextMessage, b); err != nil {
					error(err.Error())
					return
				}
			}
		}
	}(ctx)

	<-interrupt

	if err := c.WriteMessage(websocket.CloseMessage, websocket.FormatCloseMessage(websocket.CloseNormalClosure, "")); err != nil {
		log.Println("write close:", err)
		return
	}

	cancel()
	log.Println("Exit..")
}
