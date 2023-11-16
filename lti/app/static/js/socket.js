const serverState = document.getElementById("server-state");
const ws = new WebSocket(`wss://lti.lapers.net/ws/client/${email}`);

ws.onmessage = (e) => {
  handleEvent(JSON.parse(e.data));
};

ws.onclose = (e) => {
  console.log("websocket close ->\n", e.reason);
};

function handleEvent(e) {
  switch (e.event) {
    case "connected":
      serverState.textContent = "on";
      serverState.style.color = "green";
      break;
    case "disconnected":
      serverState.textContent = "off";
      serverState.style.color = "red";
      break;
    case "test_result":
      for (let test of e.args) {
        const testEl = document.getElementById(`test-${test.name}`);
        let detail;
        switch (test.result.status) {
          case "success":
            detail = document.createElement("span");
            detail.classList.add("alert", "alert-success");
            detail.textContent = "Success";
            break;
          case "failed":
            detail = document.createElement("detail");
            detail.classList.add("alert", "alert-danger");
            detail.innerHTML = `
                <summary>Error</summary>
                <pre>${test.result.error}</pre>
              `;
            break;
          default:
            detail = document.createElement("span");
            detail.textContent = "Unknown error happened!";
            detail.classList.add("alert", "alert-danger");
        }

        testEl.querySelector(".result").innerHTML = detail.outerHTML;
      }

      const score = e.args.reduce((acc, test) => {
        if (test.result.status === "success") {
          return acc + 1;
        }

        return acc;
      }, 0);

      fetch(
        `/api/score/${launchID}/${Math.trunc((score / e.args.length) * 100)}`,
        {
          method: "POST",
        }
      ).catch(console.error);
      break;
  }
}
