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
	if err := exec.Command("dockasr", "version").Run(); err != nil {
		fatal(fmt.Sprintf("check docker: %s", err.Error()))
	}
}
