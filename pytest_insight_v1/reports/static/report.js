// JavaScript for pytest-insight HTML reports

// Enable Bootstrap tooltips
document.addEventListener('DOMContentLoaded', function() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize with all test details hidden
    const detailsElements = document.querySelectorAll('.test-details');
    detailsElements.forEach(element => {
        element.style.display = 'none';
    });
    
    // Add event listeners for filter buttons
    document.querySelectorAll('.filter-btn').forEach(button => {
        button.addEventListener('click', function() {
            const outcome = this.getAttribute('data-outcome');
            filterTestsByOutcome(outcome);
            
            // Update active button
            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            this.classList.add('active');
        });
    });
    
    // Add event listener for search input
    const searchInput = document.getElementById('test-search');
    if (searchInput) {
        searchInput.addEventListener('input', searchTests);
    }
});

// Show/hide test details
function toggleTestDetails(testId) {
    const detailsElement = document.getElementById('details-' + testId);
    if (detailsElement.style.display === 'none') {
        detailsElement.style.display = 'table-row';
    } else {
        detailsElement.style.display = 'none';
    }
}

// Filter tests by outcome
function filterTestsByOutcome(outcome) {
    const testRows = document.querySelectorAll('.test-row');
    testRows.forEach(row => {
        if (outcome === 'all' || row.getAttribute('data-outcome') === outcome) {
            row.style.display = '';
            // Also hide any open details
            const index = row.getAttribute('data-index');
            const details = document.getElementById('details-' + index);
            if (details) {
                details.style.display = 'none';
            }
        } else {
            row.style.display = 'none';
        }
    });
    
    // Update count display
    updateFilteredCount();
}

// Search tests by name
function searchTests() {
    const searchInput = document.getElementById('test-search').value.toLowerCase();
    const testRows = document.querySelectorAll('.test-row');
    testRows.forEach(row => {
        const testName = row.getAttribute('data-name').toLowerCase();
        if (testName.includes(searchInput)) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
            // Also hide any open details
            const index = row.getAttribute('data-index');
            const details = document.getElementById('details-' + index);
            if (details) {
                details.style.display = 'none';
            }
        }
    });
    
    // Update count display
    updateFilteredCount();
}

// Update the count of filtered tests
function updateFilteredCount() {
    const visibleCount = document.querySelectorAll('.test-row:not([style*="display: none"])').length;
    const totalCount = document.querySelectorAll('.test-row').length;
    const countElement = document.getElementById('filtered-count');
    if (countElement) {
        countElement.textContent = `Showing ${visibleCount} of ${totalCount} tests`;
    }
}

// Export table to CSV
function exportTableToCSV(tableId, filename) {
    const table = document.getElementById(tableId);
    let csv = [];
    const rows = table.querySelectorAll('tr');
    
    for (let i = 0; i < rows.length; i++) {
        const row = [], cols = rows[i].querySelectorAll('td, th');
        
        for (let j = 0; j < cols.length; j++) {
            // Get the text content and clean it
            let text = cols[j].textContent.trim();
            // Replace double quotes with two double quotes to escape them
            text = text.replace(/"/g, '""');
            // Enclose in quotes if it contains commas, quotes, or newlines
            if (text.includes(',') || text.includes('"') || text.includes('\n')) {
                text = `"${text}"`;
            }
            row.push(text);
        }
        
        csv.push(row.join(','));
    }
    
    // Download CSV file
    downloadCSV(csv.join('\n'), filename);
}

function downloadCSV(csv, filename) {
    const csvFile = new Blob([csv], {type: "text/csv"});
    const downloadLink = document.createElement("a");
    
    // File name
    downloadLink.download = filename;
    
    // Create a link to the file
    downloadLink.href = window.URL.createObjectURL(csvFile);
    
    // Hide download link
    downloadLink.style.display = "none";
    
    // Add the link to DOM
    document.body.appendChild(downloadLink);
    
    // Click download link
    downloadLink.click();
    
    // Clean up
    document.body.removeChild(downloadLink);
}

// Print the report
function printReport() {
    window.print();
}

// Toggle dark mode
function toggleDarkMode() {
    document.body.classList.toggle('dark-mode');
    const isDarkMode = document.body.classList.contains('dark-mode');
    
    // Save preference to localStorage
    localStorage.setItem('darkMode', isDarkMode);
    
    // Update button text
    const darkModeBtn = document.getElementById('dark-mode-toggle');
    if (darkModeBtn) {
        darkModeBtn.innerHTML = isDarkMode ? 
            '<i class="bi bi-sun-fill"></i> Light Mode' : 
            '<i class="bi bi-moon-fill"></i> Dark Mode';
    }
    
    // Redraw charts if they exist
    if (typeof Plotly !== 'undefined') {
        const charts = document.querySelectorAll('[id$="-chart"]');
        charts.forEach(chart => {
            if (chart && chart._fullLayout) {
                Plotly.relayout(chart.id, {
                    paper_bgcolor: isDarkMode ? '#343a40' : '#ffffff',
                    plot_bgcolor: isDarkMode ? '#343a40' : '#ffffff',
                    font: {
                        color: isDarkMode ? '#ffffff' : '#343a40'
                    }
                });
            }
        });
    }
}
