package main

import (
	"fmt"
	"os"
	"os/exec"
)

func fatal(msg string) {
	os.Stderr.Write([]byte(msg))
	os.Exit(1)
}

func main() {
	if err := exec.Command("invalid").Run(); err != nil {
		fatal(fmt.Sprintf("exec command: %s", err.Error()))
	}
}
