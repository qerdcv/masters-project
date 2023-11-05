const tests = Array.from(document.getElementById('tests').children).map((el) => el.dataset.testName);

const runBtn = document.getElementById("btn-run")
runBtn.addEventListener('click', async () => {
    await fetch(`/tests/run/${email}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            task_id: taskId,
            tests
        })
    })
})
