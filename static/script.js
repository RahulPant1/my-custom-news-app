
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('stats-container')) {
        fetch('/api/stats')
            .then(response => response.json())
            .then(data => {
                const container = document.getElementById('stats-container');
                container.innerHTML = `
                    <p>Articles in DB: ${data.total_articles}</p>
                    <p>Processed today: ${data.processed_today}</p>
                `;
            });
    }
});
