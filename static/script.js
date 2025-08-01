document.addEventListener("DOMContentLoaded", function () {
  const today = new Date().toISOString().split("T")[0];
  const startInput = document.getElementById("startDate");
  const endInput = document.getElementById("endDate");
  const filterButton = document.getElementById("filterButton");
  const trenSelect = document.getElementById("trenRange");

  // Set default tanggal ke hari ini
  startInput.value = today;
  endInput.value = today;
  // Ambil data pertama kali saat halaman load
  fetchAllData(today, addOneDay(today), trenSelect ? trenSelect.value : "harian");
  // Event: filter tanggal
  filterButton.addEventListener("click", () => {
    const start = startInput.value;
    const end = addOneDay(endInput.value); // tambahkan 1 hari ke end
    const range = trenSelect ? trenSelect.value : "harian";
    fetchAllData(start, end, range);
  });
  // Event: dropdown tren
  if (trenSelect) {
    trenSelect.addEventListener("change", () => {
      const start = startInput.value;
      const end = addOneDay(endInput.value); // tambahkan 1 hari ke end
      const range = trenSelect.value;
      fetchAllData(start, end, range);
    });
  }

  // Tambahkan 1 hari ke string tanggal (format: YYYY-MM-DD)
  function addOneDay(dateStr) {
    const date = new Date(dateStr);
    date.setDate(date.getDate() + 1);
    return date.toISOString().split("T")[0];
  }

  function fetchAllData(start, end, range = "harian") {
    fetch(`/tren_berat?start=${start}&end=${end}&range=${range}`)
      .then((res) => res.json())
      .then((result) => {
        updateChart(result.grafik);
        updateSummary(result.summary);
        updateTren(result.tren, range);
      });
  }

  function updateChart(data) {
    const ctx = document.getElementById("grafikBerat").getContext("2d");
    const labels = data.map((d) => `${d.sayur} - ${d.grade} (${d.petani})`);
    const berat = data.map((d) => d.total_berat);

    const petaniToColor = {};
    (window.trenChart?.data?.datasets || []).forEach((ds, i) => {
      petaniToColor[ds.label] = ds.borderColor;
    });

    if (window.grafikChart) window.grafikChart.destroy();
    window.grafikChart = new Chart(ctx, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "Total Berat (kg)",
            data: berat,
            backgroundColor: data.map((d) => petaniToColor[d.petani]),
          },
        ],
      },
      options: {
        responsive: true,
        scales: { y: { beginAtZero: true } },
        plugins: {
          legend: {
            display: true,
            labels: { usePointStyle: true, pointStyle: "line", color: "#000" },
          },
          tooltip: {
            callbacks: {
              label: (ctx) => `${ctx.dataset.label}: ${ctx.raw.toLocaleString("id-ID", { minimumFractionDigits: 3 })} kg`,
            },
          },
        },
      },
    });
  }

  function updateSummary(summary) {
    const container = document.getElementById("petaniSummaryContainer");
    container.innerHTML = "";
    for (const petani in summary) {
      const card = document.createElement("div");
      card.className = "petani-card";
      const title = document.createElement("h3");
      title.textContent = petani;
      card.appendChild(title);
      let totalBeratPetani = 0;
      summary[petani].forEach((item) => {
        const p = document.createElement("p");
        p.textContent = `${item.sayur} - Grade ${item.grade} : ${item.total_berat.toLocaleString("id-ID", { minimumFractionDigits: 2 })} kg`;
        card.appendChild(p);
        totalBeratPetani += item.total_berat;
      });
      const totalElem = document.createElement("h3");
      totalElem.textContent = `Total : ${totalBeratPetani.toLocaleString("id-ID", { minimumFractionDigits: 2 })} kg`;
      totalElem.style.marginTop = "10px";
      card.appendChild(totalElem);
      container.appendChild(card);
    }
  }

  function updateTren(data, range) {
    const ctx = document.getElementById("grafikTren").getContext("2d");
    const labels = data.labels.map((label) => (/^\d{4}-\d{2}-\d{2}$/.test(label) ? label : new Date(label).toISOString().split("T")[0]));
    window.trenChart?.destroy();
    window.trenChart = new Chart(ctx, {
      type: "line",
      data: { labels, datasets: data.datasets },
      options: {
        responsive: true,
        interaction: { mode: "nearest", intersect: false },
        plugins: {
          tooltip: {
            mode: "nearest",
            intersect: false,
            callbacks: {
              label: (ctx) => `${ctx.dataset.label}: ${ctx.raw.toLocaleString("id-ID", { minimumFractionDigits: 2 })} kg`,
            },
          },
          legend: { position: "top" },
        },
        scales: {
          y: {
            beginAtZero: true,
            title: { display: true, text: "Berat (kg)" },
          },
          x: {
            title: {
              display: true,
              text: range[0].toUpperCase() + range.slice(1),
            },
          },
        },
      },
    });
  }
});
