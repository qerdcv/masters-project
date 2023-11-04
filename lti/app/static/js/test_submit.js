const submitButton = document.getElementById('submit');
submitButton.addEventListener('click', function (e) {
    const data = new FormData();
    data.append('description', document.getElementById('description').value)
    data.append('task_id', taskId)

    const tests = document.getElementById('tests');

    for (let test of tests.children) {
        const inputs = test.querySelectorAll('input');

        const descInput = inputs[0];
        const fileInput = inputs[1];

        data.append(descInput.name, descInput.value)
        data.append(fileInput.name, fileInput.files[0])
    }
    console.log(data.entries());
    fetch('/tests', {
        method: 'POST',
        body: data
    }).catch(console.error);
})