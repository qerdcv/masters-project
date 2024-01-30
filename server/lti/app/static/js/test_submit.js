const form = document.getElementById('tests-form');
const uploadResult = document.getElementById('upload-result');
form.addEventListener('submit', function (e) {
    e.preventDefault();

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

    fetch('/tests', {
        method: 'POST',
        body: data
    }).then(() => {
        const el = document.createElement('span');
        el.classList.add('alert', 'alert-success');
        el.textContent = 'Success!'
        uploadResult.innerHTML = el.outerHTML;
        setTimeout(() => uploadResult.innerHTML = '', 2000);
    }).catch((e) => {
        const el = document.createElement('span');
        el.classList.add('alert', 'alert-danger');
        el.textContent = 'Failed!';
        uploadResult.innerHTML = el.outerHTML;
        setTimeout(() => uploadResult.innerHTML = '', 2000);
    });
})