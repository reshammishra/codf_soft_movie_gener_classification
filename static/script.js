// Runs on the dashboard page only
const plotBox = document.getElementById("plot");
const countText = document.getElementById("count");
const button = document.getElementById("predict-btn");
const errorBox = document.getElementById("error");
const resultBox = document.getElementById("result");
const mainGenre = document.getElementById("main-genre");
const genreList = document.getElementById("genre-list");

// Live character counter
plotBox.addEventListener("input", () => {
  countText.textContent = plotBox.value.length;
});

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
  resultBox.classList.add("hidden");
}

button.addEventListener("click", async () => {
  const plot = plotBox.value.trim();
  errorBox.classList.add("hidden");

  // Basic validation before sending to the server
  if (plot === "") {
    showError("Please enter a plot summary.");
    return;
  }
  if (plot.split(/\s+/).length < 5) {
    showError("Please enter at least 5 words.");
    return;
  }

  button.disabled = true;
  button.textContent = "Predicting...";

  try {
    // Send the plot to Flask, which uses the trained model
    const response = await fetch("/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plot: plot }),
    });

    if (response.status === 401) {
      window.location.href = "/login";   // session expired
      return;
    }

    const data = await response.json();
    if (!response.ok) {
      showError(data.error || "Something went wrong.");
      return;
    }
    showResult(data.predictions);
  } catch (err) {
    showError("Could not reach the server. Is Flask running?");
  } finally {
    button.disabled = false;
    button.textContent = "Predict Genre";
  }
});

function showResult(predictions) {
  // Top prediction is shown large
  mainGenre.textContent = predictions[0].genre;

  // All top predictions listed with a small bar
  genreList.innerHTML = "";
  predictions.forEach((p) => {
    const li = document.createElement("li");

    const row = document.createElement("div");
    row.className = "genre-row";
    const name = document.createElement("span");
    name.textContent = p.genre;
    const score = document.createElement("span");
    score.textContent = p.score + "%";
    row.appendChild(name);
    row.appendChild(score);

    const bar = document.createElement("div");
    bar.className = "bar";
    const fill = document.createElement("div");
    fill.className = "bar-fill";
    fill.style.width = Math.min(p.score, 100) + "%";
    bar.appendChild(fill);

    li.appendChild(row);
    li.appendChild(bar);
    genreList.appendChild(li);
  });

  resultBox.classList.remove("hidden");
}