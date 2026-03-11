// counter.js - live stats counter on the homepage
// polls /platform-stats every 30s
// Copilot showed me the requestAnimationFrame count-up trick

(function () {
    'use strict';

    const bdtCounter = document.getElementById('bdt-counter');
    const gigsCounter = document.getElementById('gigs-counter');
    const studentsCounter = document.getElementById('students-counter');

    if (!bdtCounter) return;

    let currentBdt = 0;
    let currentGigs = 0;
    let currentStudents = 0;

    // animate number counting up
    function animateCount(element, start, end, duration, suffix) {
        if (start === end) {
            element.textContent = formatNumber(end) + (suffix || '');
            return;
        }

        const startTime = performance.now();
        const diff = end - start;

        function step(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);

            // ease out
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = Math.round(start + diff * eased);

            element.textContent = formatNumber(current) + (suffix || '');

            if (progress < 1) {
                requestAnimationFrame(step);
            }
        }

        requestAnimationFrame(step);
    }

    function formatNumber(num) {
        return new Intl.NumberFormat().format(num);
    }

    function fetchStats() {
        fetch('/platform-stats')
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (data.total_bdt_earned !== currentBdt) {
                    animateCount(bdtCounter, currentBdt, data.total_bdt_earned, 1000, ' BDT');
                    currentBdt = data.total_bdt_earned;
                }

                if (gigsCounter && data.total_gigs_completed !== currentGigs) {
                    animateCount(gigsCounter, currentGigs, data.total_gigs_completed, 800);
                    currentGigs = data.total_gigs_completed;
                }

                if (studentsCounter && data.active_students !== currentStudents) {
                    animateCount(studentsCounter, currentStudents, data.active_students, 800);
                    currentStudents = data.active_students;
                }
            })
            .catch(function (err) {
                console.error('Failed to fetch platform stats:', err);
            });
    }

    // Initial fetch
    fetchStats();

    // Poll every 30 seconds
    setInterval(fetchStats, 30000);
})();
