// filters.js - auto-submit the gig filter form on dropdown change

(function () {
    'use strict';

    const filterForm = document.getElementById('filter-form');
    if (!filterForm) return;

    // Auto-submit when category or rating dropdown changes
    const categorySelect = document.getElementById('filter-category');
    const ratingSelect = document.getElementById('filter-rating');

    if (categorySelect) {
        categorySelect.addEventListener('change', function () {
            filterForm.submit();
        });
    }

    if (ratingSelect) {
        ratingSelect.addEventListener('change', function () {
            filterForm.submit();
        });
    }

    // Submit on Enter in keyword field
    const keywordInput = document.getElementById('filter-keyword');
    if (keywordInput) {
        keywordInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                filterForm.submit();
            }
        });
    }
})();
