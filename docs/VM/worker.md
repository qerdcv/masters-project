# Virtual Machine Worker

Virtual machine workers - is a program that is running on the virtual machine, and listens for the events.

Event - is what needs to be executed in the virtual machine and task related to the test (created by teacher).

The all logic of the service - is to connect to the servers websocket endpoint using student`s email, and wait for events.

## Streaming

Worker, and client side (web-site) is implementing streaming mechanism. For streaming protocol were used WebSockets.

## Stream event

In the current implementation event has next structure:

```json
{
  "task_id": "1",
  "test": "docker_test"
}
```

Using following information worker downloading executable file from the server (path is formed like `/tests/download/<task_id>/<test>`), and executes it.

After test execution worker should return `testResult` object, that represents the result of the test execution.
`testResult` has next structure

```json
{
  "name": "docker_test",
  "result": {
    "status": "string", // enum: success, failed
    "error": "string"   // optional. If result.status is "failed" - this field will contain failure details
  }
}
```
