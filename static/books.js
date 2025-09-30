// static/js/books.js

document.addEventListener('DOMContentLoaded', function() {
    // Borrow book functionality for members
    const borrowButtons = document.querySelectorAll('.borrow-btn');
    borrowButtons.forEach(button => {
        button.addEventListener('click', function() {
            const bookId = this.getAttribute('data-book-id');
            const button = this;
            
            button.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Borrowing...';
            button.disabled = true;
            
            fetch('/api/borrow_book', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    book_id: bookId
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showAlert('success', data.message);
                    // Update the availability status
                    const card = button.closest('.card');
                    const badge = card.querySelector('.availability-badge');
                    badge.className = 'availability-badge badge bg-danger';
                    badge.textContent = 'Checked Out';
                    button.remove();
                } else {
                    showAlert('error', data.message);
                    button.innerHTML = '<i class="fas fa-bookmark me-1"></i>Borrow';
                    button.disabled = false;
                }
            })
            .catch(error => {
                showAlert('error', 'Network error. Please try again.');
                button.innerHTML = '<i class="fas fa-bookmark me-1"></i>Borrow';
                button.disabled = false;
            });
        });
    });

    // Edit book functionality for admin/librarian
    const editButtons = document.querySelectorAll('.edit-book-btn');
    const editModal = new bootstrap.Modal(document.getElementById('editBookModal'));
    
    editButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Populate the edit form with book data
            document.getElementById('editBookId').value = this.getAttribute('data-book-id');
            document.getElementById('editIsbn').value = this.getAttribute('data-book-isbn');
            document.getElementById('editTitle').value = this.getAttribute('data-book-title');
            document.getElementById('editEdition').value = this.getAttribute('data-book-edition');
            document.getElementById('editPublicationYear').value = this.getAttribute('data-book-publication-year');
            document.getElementById('editPages').value = this.getAttribute('data-book-pages');
            document.getElementById('editAuthorId').value = this.getAttribute('data-book-author-id');
            document.getElementById('editPublisherId').value = this.getAttribute('data-book-publisher-id');
            document.getElementById('editCategoryId').value = this.getAttribute('data-book-category-id');
            document.getElementById('editDescription').value = this.getAttribute('data-book-description');
            document.getElementById('editTotalCopies').value = this.getAttribute('data-book-total-copies');
            document.getElementById('editLocation').value = this.getAttribute('data-book-location');
            
            // Show the edit modal
            editModal.show();
        });
    });
    
    // Handle edit form submission
    const editForm = document.querySelector('#editBookModal form');
    if (editForm) {
        editForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData(this);
            const submitButton = this.querySelector('button[type="submit"]');
            
            submitButton.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Updating...';
            submitButton.disabled = true;
            
            fetch('/edit_book', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showAlert('success', data.message);
                    editModal.hide();
                    // Reload the page to show updated data
                    setTimeout(() => {
                        location.reload();
                    }, 1500);
                } else {
                    showAlert('error', data.message);
                    submitButton.innerHTML = 'Update Book';
                    submitButton.disabled = false;
                }
            })
            .catch(error => {
                showAlert('error', 'Network error. Please try again.');
                submitButton.innerHTML = 'Update Book';
                submitButton.disabled = false;
            });
        });
    }

    // Delete book functionality
    const deleteButtons = document.querySelectorAll('.delete-book-btn');
    deleteButtons.forEach(button => {
        button.addEventListener('click', function() {
            const bookId = this.getAttribute('data-book-id');
            const bookTitle = this.getAttribute('data-book-title');
            
            if (confirm(`Are you sure you want to delete "${bookTitle}"? This action cannot be undone.`)) {
                const button = this;
                button.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
                button.disabled = true;
                
                fetch('/delete_book', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        book_id: bookId
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        showAlert('success', data.message);
                        // Remove the book card from the page
                        button.closest('.col-md-6').remove();
                    } else {
                        showAlert('error', data.message);
                        button.innerHTML = '<i class="fas fa-trash"></i>';
                        button.disabled = false;
                    }
                })
                .catch(error => {
                    showAlert('error', 'Network error. Please try again.');
                    button.innerHTML = '<i class="fas fa-trash"></i>';
                    button.disabled = false;
                });
            }
        });
    });

    // Utility function to show alerts
    function showAlert(type, message) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type === 'success' ? 'success' : 'danger'} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-triangle'} me-2"></i>${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        const mainContainer = document.querySelector('.mb-4');
        if (mainContainer) {
            mainContainer.appendChild(alertDiv);
        } else {
            document.querySelector('.container').prepend(alertDiv);
        }
        
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }
});