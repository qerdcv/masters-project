/*
    This module is mostly the core of the client side of the student`s page.
    It responsible for running tests, and passing marks to the backend.
*/

// cache of test names
const tests = Array.from(document.getElementById("tests").children).map(
  (el) => el.dataset.testName
);

const runBtn = document.getElementById("btn-run");
runBtn.addEventListener("click", (e) => {
  // handling of the "run" button click
  e.target.disabled = true;

  // all tests is running asynchronously
  Promise.all(
    tests.map(
      (test) =>
        new Promise((resolve, reject) => {
          // part that adds loader to the specific test
          const testEl = document.getElementById(`test-${test}`);
          const loader = document.createElement("div");
          loader.classList.add("spinner-border");
          testEl.querySelector(".result").innerHTML = loader.outerHTML;

          try {
            // run test request
            fetch(`/tests/run/${email}`, {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                task_id: taskId,
                test,
              }),
            })
              .then((resp) => resolve(resp.json()))
              .catch((e) => reject(e));
          } catch (e) {
            reject(e);
          }
        })
    )
  )
    .then((responses) => {
      // score is represented by count of the tests that has success status in the response
      const score = responses.reduce((acc, resp) => {
        if (resp.result.status === "success") {
          return acc + 1;
        }

        return acc;
      }, 0);

      // and after our calculations - it puts the mark in the LMS for the student based on the count of successfully run tests
      fetch(
        `/api/score/${launchID}/${Math.trunc(
          (score / responses.length) * 100
        )}`,
        {
          method: "POST",
        }
      ).catch(console.error);
    })
    .catch(console.error);

  e.target.disabled = false;
});
