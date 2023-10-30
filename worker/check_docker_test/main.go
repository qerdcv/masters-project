package main

import (
	"log"
	"os/exec"
)

func main() {
	if err := exec.Command("dockasr", "version").Run(); err != nil {
		log.Fatalf("check docker: %s", err.Error())
	}
}
