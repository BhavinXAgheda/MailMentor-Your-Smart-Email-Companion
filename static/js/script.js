document.addEventListener('DOMContentLoaded', () => {
    const searchButton = document.getElementById('searchButton');
    const searchInput = document.getElementById('searchInput');
    const resultsContainer = document.getElementById('resultsContainer');

    // --- Search Functionality ---
    const performSearch = async () => {
        const query = searchInput.value.trim();
        if (!query) {
            resultsContainer.innerHTML = '<p class="placeholder">Please enter a search query.</p>';
            return;
        }
        resultsContainer.innerHTML = '<p class="placeholder">Searching...</p>';
        try {
            const response = await fetch('/api/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query }),
            });
            if (!response.ok) throw new Error(`HTTP error! Status: ${response.status}`);
            const results = await response.json();
            displayResults(results);
        } catch (error) {
            console.error('Search failed:', error);
            resultsContainer.innerHTML = '<p class="placeholder">An error occurred during search.</p>';
        }
    };

    const displayResults = (emails) => {
        if (!emails || emails.length === 0) {
            resultsContainer.innerHTML = '<p class="placeholder">No results found.</p>';
            return;
        }
        resultsContainer.innerHTML = emails.map(email => `
            <div class="email-item" id="email-${email.id}">
                <div class="email-header">
                    <span class="email-sender">${escapeHTML(email.sender)}</span>
                    <span class="email-distance">Similarity: ${Number(email.distance).toFixed(3)}</span>
                </div>
                <div class="email-subject">${escapeHTML(email.subject)}</div>
                <div class="email-body">${escapeHTML(email.body)}</div>
                <div class="email-actions">
                    <button class="summarize-btn" data-email-id="${email.id}">Summarize</button>
                </div>
                <div class="summary-container" id="summary-for-${email.id}" style="display: none;"></div>
            </div>
        `).join('');
    };

    // --- Summarization Functionality ---
    const startSummarization = async (emailId, button) => {
        button.disabled = true;
        button.textContent = 'Summarizing...';
        const summaryContainer = document.getElementById(`summary-for-${emailId}`);
        summaryContainer.style.display = 'block';
        summaryContainer.innerHTML = 'Generating summary, please wait...';

        try {
            const response = await fetch(`/api/summarize/${emailId}`, { method: 'POST' });
            if (response.status !== 202) throw new Error('Failed to start summarization task.');
            
            const data = await response.json();
            pollTaskStatus(data.task_id, summaryContainer, button);
        } catch (error) {
            console.error('Summarization failed:', error);
            summaryContainer.innerHTML = 'Error starting summarization.';
            button.disabled = false;
            button.textContent = 'Summarize';
        }
    };

    const pollTaskStatus = async (taskId, container, button) => {
        const interval = setInterval(async () => {
            try {
                const response = await fetch(`/api/task-status/${taskId}`);
                const data = await response.json();

                if (data.status === 'SUCCESS') {
                    clearInterval(interval);
                    const summaryResult = data.result;
                    if (summaryResult.status === 'success') {
                        container.innerHTML = `<strong>Summary:</strong> ${escapeHTML(summaryResult.summary)}`;
                    } else {
                        container.innerHTML = `<strong>Error:</strong> ${escapeHTML(summaryResult.message)}`;
                    }
                    button.style.display = 'none'; // Hide button after success
                } else if (data.status === 'FAILURE') {
                    clearInterval(interval);
                    container.innerHTML = '<strong>Error:</strong> Task failed to generate summary.';
                    button.disabled = false;
                    button.textContent = 'Retry Summarize';
                }
                // If status is PENDING or STARTED, the loop continues
            } catch (error) {
                clearInterval(interval);
                console.error('Polling failed:', error);
                container.innerHTML = 'Error checking summary status.';
                button.disabled = false;
                button.textContent = 'Retry Summarize';
            }
        }, 2000); // Check every 2 seconds
    };

    // --- Utility Function ---
    const escapeHTML = (str) => {
        if (str === null || str === undefined) return '';
        const p = document.createElement('p');
        p.textContent = str;
        return p.innerHTML;
    };

    // --- Event Listeners ---
    searchButton.addEventListener('click', performSearch);
    searchInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter') performSearch();
    });

    // Event delegation for dynamically created summarize buttons
    resultsContainer.addEventListener('click', (event) => {
        if (event.target && event.target.classList.contains('summarize-btn')) {
            const emailId = event.target.dataset.emailId;
            startSummarization(emailId, event.target);
        }
    });
});
