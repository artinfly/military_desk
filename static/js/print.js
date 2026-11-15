document.querySelectorAll('[data-print]').forEach(button => {
    button.addEventListener('click', () => {
        document.body.classList.toggle('print-right', button.dataset.print === 'right');
        window.print();
    });
});

window.addEventListener('afterprint', () => document.body.classList.remove('print-right'));
