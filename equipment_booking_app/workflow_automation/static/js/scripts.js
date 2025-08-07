// Consolidated JavaScript for Automation project

document.addEventListener('DOMContentLoaded', function() {
    // Sidebar toggle
    const toggleBtn = document.getElementById('sidebarToggle');
    const sidebar = document.getElementById('sidebar');
    const logo = document.getElementById('sidebarLogo');
    if (toggleBtn && sidebar) {
        const openLogo = logo ? logo.dataset.openLogo : null;
        const collapsedLogo = logo ? logo.dataset.collapsedLogo : null;
        const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
        if (isCollapsed) {
            sidebar.classList.add('collapsed');
            document.body.classList.add('sidebar-collapsed');
            if (logo && collapsedLogo) logo.src = collapsedLogo;
        } else if (logo && openLogo) {
            logo.src = openLogo;
        }
        toggleBtn.addEventListener('click', function() {
            sidebar.classList.toggle('collapsed');
            document.body.classList.toggle('sidebar-collapsed');
            const collapsed = sidebar.classList.contains('collapsed');
            if (logo && openLogo && collapsedLogo) {
                logo.src = collapsed ? collapsedLogo : openLogo;
            }
            localStorage.setItem('sidebarCollapsed', collapsed);
        });
    }

    // Generic confirmations
    document.querySelectorAll('.confirm-link').forEach(function(link){
        link.addEventListener('click', function(e){
            const msg = link.dataset.confirm || 'Are you sure?';
            if(!confirm(msg)){
                e.preventDefault();
            }
        });
    });
    document.querySelectorAll('.confirm-form').forEach(function(form){
        form.addEventListener('submit', function(e){
            const msg = form.dataset.confirm || 'Are you sure?';
            if(!confirm(msg)){
                e.preventDefault();
            }
        });
    });

    // Status filter for My Workflows
    const statusFilter = document.getElementById('statusFilter');
    if (statusFilter) {
        statusFilter.addEventListener('change', function() {
            const filter = this.value;
            document.querySelectorAll('#my-workflows tbody tr').forEach(function(row) {
                row.style.display = !filter || row.dataset.status === filter ? '' : 'none';
            });
        });
    }

    // Helper for folder pickers
    function setupFolderPicker(btnId, pickerId, fieldId, labelId, callback) {
        const btn = document.getElementById(btnId);
        const picker = document.getElementById(pickerId);
        if (btn && picker) {
            btn.addEventListener('click', () => picker.click());
            picker.addEventListener('change', () => {
                if (picker.files.length) {
                    const file = picker.files[0];
                    const path = file.path || file.webkitRelativePath.split('/')[0];
                    if (fieldId) {
                        const field = document.getElementById(fieldId);
                        if (field) field.value = path;
                    }
                    if (labelId) {
                        const label = document.getElementById(labelId);
                        if (label) label.textContent = path;
                    }
                    if (callback) callback(path);
                }
            });
        }
    }

    // Simple pickers (Zip/Convert)
    if (document.getElementById('input_folder_btn') && !document.getElementById('single-folder')) {
        setupFolderPicker('input_folder_btn','input_folder_picker','id_input_path','input_folder_label');
    }
    if (document.getElementById('output_folder_btn') && document.getElementById('id_output_zip')) {
        setupFolderPicker('output_folder_btn','output_folder_picker','id_output_zip','output_folder_label');
    }

    // Run Rename
    function renameCheckVisibility() {
        const raw = document.getElementById('id_raw_data_folder');
        const out = document.getElementById('id_output_folder');
        const fields = document.getElementById('additional-fields');
        if (raw && out && fields && raw.value && out.value) {
            fields.classList.remove('d-none');
        }
    }
    setupFolderPicker('raw_folder_btn','raw_folder_picker','id_raw_data_folder','raw_folder_label', renameCheckVisibility);
    setupFolderPicker('output_folder_btn','output_folder_picker','id_output_folder','output_folder_label', function(path){
        const renameField = document.getElementById('id_rename_pattern');
        if (renameField && !renameField.value) {
            const base = path.replace(/[\\/]+$/, '').split(/[\\/]/).pop();
            renameField.value = `${base}-3V-{timestamp}{ext}`;
        }
        renameCheckVisibility();
    });
    renameCheckVisibility();

    // Run Workflow
    function updatePickers() {
        const sameEl = document.querySelector('input[name="use_input_path"]:checked');
        const single = document.getElementById('single-folder');
        const two = document.getElementById('two-folders');
        if (sameEl && single && two) {
            if (sameEl.value === 'True') {
                single.classList.remove('d-none');
                two.classList.add('d-none');
            } else {
                single.classList.add('d-none');
                two.classList.remove('d-none');
            }
        }
    }
    if (document.getElementById('single-folder')) {
        updatePickers();
        document.querySelectorAll('input[name="use_input_path"]').forEach(function(el){
            el.addEventListener('change', updatePickers);
        });
        setupFolderPicker('input_folder_btn','input_folder_picker','id_input_path','input_folder_label', function(path){
            const outField = document.getElementById('id_output_path');
            if (outField) outField.value = path;
        });
        setupFolderPicker('input_folder_btn2','input_folder_picker2','id_input_path','input_folder_label2');
        setupFolderPicker('output_folder_btn','output_folder_picker','id_output_path','output_folder_label');

        document.querySelectorAll('.raw-picker-btn').forEach(function(btn){
            btn.addEventListener('click', function(){
                const picker = document.getElementById(btn.dataset.picker);
                if (picker) picker.click();
            });
        });
        document.querySelectorAll('input[id^="raw_picker_"]').forEach(function(picker){
            picker.addEventListener('change', function(){
                if (picker.files.length) {
                    const file = picker.files[0];
                    const path = file.path || file.webkitRelativePath.split('/')[0];
                    const counter = picker.id.split('_')[2];
                    const field = document.getElementById('id_form-' + (counter - 1) + '-raw_data_folder');
                    const label = document.getElementById('raw_label_' + counter);
                    if (field) field.value = path;
                    if (label) label.textContent = path;
                }
            });
        });
        const videoList = document.getElementById('video-list');
        if (videoList) {
            const updateOrder = () => {
                videoList.querySelectorAll('li').forEach((li, idx) => {
                    li.querySelector('input[name$="-order"]').value = idx + 1;
                });
            };
            let dragItem = null;
            videoList.addEventListener('dragstart', e => { dragItem = e.target.closest('li'); });
            videoList.addEventListener('dragover', e => { e.preventDefault(); });
            videoList.addEventListener('drop', e => {
                e.preventDefault();
                const target = e.target.closest('li');
                if (dragItem && target && dragItem !== target) {
                    videoList.insertBefore(dragItem, target);
                    updateOrder();
                }
            });
            updateOrder();
        }
    }

    // Create Workflow toggles
    document.querySelectorAll('.task-toggle').forEach(function(cb){
        cb.addEventListener('change', function(){
            const target = document.getElementById(cb.dataset.target);
            if (target) {
                target.style.display = cb.checked ? 'block' : 'none';
            }
        });
    });
});

