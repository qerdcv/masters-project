const tests = Array.from(document.getElementById('tests').children).map((el) => el.dataset.testName);

const runBtn = document.getElementById("btn-run")
runBtn.addEventListener('click', (e) => {
    e.target.disabled = true;

    Promise.all(tests.map((test) => new Promise((resolve, reject) => {
        const testEl = document.getElementById(`test-${test}`);
        const loader = document.createElement("div");
        loader.classList.add("spinner-border");
        testEl.querySelector(".result").innerHTML = loader.outerHTML;

        try {
            fetch(`/tests/run/${email}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    task_id: taskId,
                    test
                })
            }).then(
                resp => resolve(resp.json())
            ).catch(e => reject(e));
        } catch (e) {
            reject(e);
        }
    }))).then((responses) => {
        const score = responses.reduce((acc, resp) => {
            if (resp.result.status === "success") {
                return acc + 1;
            }

            return acc;
        }, 0);

        fetch(
            `/api/score/${launchID}/${Math.trunc((score / responses.length) * 100)}`,
            {
                method: "POST",
            }
        ).catch(console.error);
    }).catch(console.error);

    e.target.disabled = false;
})
