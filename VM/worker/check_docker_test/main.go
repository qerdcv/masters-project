/*
	This is a example test program, that checks for docker via simple `docker ps` command.
	If there is no docker installed - it will return an error, something like (cannot find executable `docker`)
*/

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
	if err := exec.Command("docker", "ps").Run(); err != nil {
		fatal(fmt.Sprintf("exec command: %s", err.Error()))
	}
}
