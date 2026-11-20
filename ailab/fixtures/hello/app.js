let n = 0;
document.getElementById("count").addEventListener("click", e => { n += 1; e.target.textContent = `Tapped ${n} times`; });
