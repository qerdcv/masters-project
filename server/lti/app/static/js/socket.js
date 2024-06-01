/*
    This module is needed to handle events that comes from backend via websockets
*/

const serverState = document.getElementById("server-state");
const ws = new WebSocket(`wss://lti.lapers.net/ws/client/${email}`);

ws.onmessage = (e) => {
  handleEvent(JSON.parse(e.data));
};

ws.onclose = (e) => {
  console.log("websocket closed ", e.reason);
};

function handleEvent(e) {
  // based on the event type - there is different actions
  switch (e.event) {
    case "connected":
      // this event signalize that student`s virtual machine is connected to the backend
      serverState.textContent = "on";
      serverState.style.color = "green";
      break;
    case "disconnected":
      // this event signalize that student`s virtual machine is disconnected from the backend
      serverState.textContent = "off";
      serverState.style.color = "red";
      break;
    case "test_result":
      // this event received, when backend has prepared test result for the specific run
      // it has pretty straight forward logic.
      // tests is rendered in the students page with some id`s (test-<test_name>.
      // result event should posses this name to determine for what tests this result.
      // Test result has 2 statuses:
      //   1. success - test is passed successfully (just mark this test as succeed)
      //   2. failed - test has been failed. For every failed test - backed should also provide information about failure (error message)
      //      So it renders details element with error message
      const test = e.args;
      const testEl = document.getElementById(`test-${test.name}`);
      let detail;
      switch (test.result.status) {
        case "success":
          detail = document.createElement("span");
          detail.classList.add("alert", "alert-success");
          detail.textContent = "Success";
          break;
        case "failed":
          const errorMessage = test.result.error.replace("<nil>", "null");
          detail = document.createElement("details");
          detail.classList.add("alert", "alert-danger");
          detail.innerHTML = `
              <summary>Error</summary>
              <pre>${errorMessage}</pre>
            `;
          break;
        default:
          detail = document.createElement("span");
          detail.textContent = "Unknown error happened!";
          detail.classList.add("alert", "alert-danger");

          break;
      }

      // inject previously generated element to the test result
      testEl.querySelector(".result").innerHTML = detail.outerHTML;
  }
}
