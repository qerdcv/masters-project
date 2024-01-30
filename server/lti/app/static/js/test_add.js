let addBtn = document.getElementById("add-btn");
const tests = document.getElementById("tests");

addBtn.addEventListener('click', handleAddClick)

function handleAddClick(e) {
    e.preventDefault();

    const prevTest = document.getElementById(`test-${dataIndex}`);
    addBtn.remove();

    prevTest.appendChild(createRemoveButton(dataIndex));

    dataIndex += 1;

    tests.appendChild(createTestRow(dataIndex));
}

function createTestRow(dataIndex) {
    const testRow = document.createElement('div')
    testRow.classList.add('d-flex', 'flex-row', 'justify-content-between', 'mb-3');
    testRow.id = `test-${dataIndex}`;
    const testNameInput = document.createElement('input')
    testNameInput.name = `test-description-${dataIndex}`;
    testNameInput.classList.add('form-control', 'mx-2');
    testNameInput.placeholder = 'Test description';
    testNameInput.required = true;
    testRow.appendChild(testNameInput);
    const testFile = document.createElement('input');
    testFile.type = 'file';
    testFile.name = `test-file-${dataIndex}`
    testFile.id = `test-file-${dataIndex}`
    testFile.required = true;
    testFile.classList.add('form-control', 'mx-2');
    testRow.appendChild(testFile)
    testRow.appendChild(addBtn);
    return testRow
}

function createRemoveButton() {
    const btn = document.createElement('button')
    btn.classList.add('btn', 'btn-danger');
    btn.textContent = '-';
    btn.addEventListener('click', handleRemoveClick);

    return btn;
}

function handleRemoveClick(e) {
        e.preventDefault();
        e.target.parentElement.remove();
}