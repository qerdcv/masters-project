const serverState = document.getElementById("server-state");
const ws = new WebSocket(`wss://lti.lapers.net/ws/client/${email}`);

ws.onmessage = (e) => {
    handleEvent(JSON.parse(e.data));
};

ws.onclose = (e) => {
    console.log("websocket closed ", e.reason);
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

            testEl.querySelector(".result").innerHTML = detail.outerHTML;
    }
}
