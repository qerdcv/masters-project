const serverState = document.getElementById('server-state');
const ws = new WebSocket(`ws://192.168.31.57:9001/ws/client/${email}`);

ws.onmessage = (e) => {
    handleEvent(JSON.parse(e.data));
};

ws.onclose = (e) => {
    console.log('websocket close ->\n', e.reason);
};

function handleEvent(e) {
    switch (e.event) {
    case 'connected':
        serverState.textContent = 'on';
        serverState.style.color = 'green';
        break;
    case 'disconnected':
        serverState.textContent = 'off';
        serverState.style.color = 'red';
        break;
        case 'test_result':
        for (let test of e.args) {
            const testEl = document.getElementById(`test-${test.name}`);

            console.log(test);
            const detail = document.createElement('span')
            if (test.result.status === 'success') {
                detail.textContent = ' Success'
                detail.style.color = 'green'
            } else {
                detail.textContent = ' Error: ' + test.result.error;
                detail.style.color = 'red';

            }

            testEl.appendChild(detail);
        }

        // todo: move grades to the server side
        const score = e.args.reduce((acc, test) => {
            if (test.result.status === 'success') {
                return acc + 1;
            }

            return acc;
        }, 0);

        console.log(score, e.args.length);
        fetch(`/api/score/${launchID}/${Math.trunc((score / e.args.length) * 100)}`, {
            method: 'POST'
        }).catch(console.error)
        break;
    }
}