let activeTargetUser = ""; let activeFolderType = "";

function openWindow(id) { 
    document.getElementById(id).style.display = 'flex'; 
    if(id === 'adminWindow') updateLiveDiskQuotaVisuals();
}
function closeWindow(id) { document.getElementById(id).style.display = 'none'; }

function openExplorer(username) {
    activeTargetUser = username;
    document.getElementById('explorerTitle').innerText = username + "'s Folders";
    document.getElementById('fileListContainer').innerHTML = `<tr><td colspan="6" style="text-align:center; padding:15px; color:gray;">Click Public or Private components in the sidebar panel.</td></tr>`;
    document.getElementById('uploadForm').style.display = 'none';
    document.getElementById('dragDropVisualTarget').style.display = 'none';
    openWindow('explorerWindow');
}

function loadFolder(folderType) {
    activeFolderType = folderType;
    let container = document.getElementById('fileListContainer');
    container.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:15px; color:#0054e3; font-weight:bold;">⏳ Reading directory...</td></tr>`;
    
    fetch(`/api/explore/${activeTargetUser}/${folderType}`)
        .then(res => { if(!res.ok) throw new Error(); return res.json(); })
        .then(data => {
            if(data.files.length === 0) { 
                container.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:20px; color:gray; font-style:italic;">Directory folder is completely empty.</td></tr>`; 
            } else {
                container.innerHTML = "";
                data.files.forEach(f => {
                    let tr = document.createElement('tr');
                    let deleteMarkup = f.allow_delete ? `<button class="delete-action-btn" onclick="deleteTargetFile('${f.name}')">❌ Delete</button>` : '<span style="color:gray;">Locked</span>';
                    tr.innerHTML = `
                        <td style="font-weight:bold; color:#1a3b75;">📄 ${f.name}</td>
                        <td>${Math.round(f.size/1024)} KB</td>
                        <td style="color:#226e27; font-weight:bold;">${f.uploaded_by}</td>
                        <td style="color:#555;">${f.timestamp}</td>
                        <td style="font-style:italic; color:#444;">${f.remark}</td>
                        <td class="file-actions-row"><a href="/api/download/${activeTargetUser}/${activeFolderType}/${f.name}">📥 Download</a>${deleteMarkup}</td>
                    `;
                    container.appendChild(tr);
                });
            }
            document.getElementById('uploadForm').style.display = 'block';
            document.getElementById('dragDropVisualTarget').style.display = 'block';
        })
        .catch(err => {
            container.innerHTML = `<tr><td colspan="6" style="text-align:center; color:red; font-weight:bold; padding:20px;">❌ Access Violation: Security isolation barriers enforce folder lock bounds.</td></tr>`;
            document.getElementById('uploadForm').style.display = 'none';
            document.getElementById('dragDropVisualTarget').style.display = 'none';
        });
}

function handleManualUploadSubmit(e) {
    e.preventDefault();
    let fileInput = document.getElementById('manualFileInput');
    let remarkInput = document.getElementById('manualRemarkInput');
    if(fileInput.files.length === 0) return;
    executeAsynchronousUploadPipeline(fileInput.files[0], remarkInput.value);
    remarkInput.value = "";
    fileInput.value = "";
}

function executeAsynchronousUploadPipeline(fileObj, remarkText) {
    let loader = document.getElementById('loadingProgressBox');
    loader.style.display = 'block';
    let formData = new FormData();
    formData.append('file', fileObj);
    formData.append('remark', remarkText || "No remark provided.");
    
    fetch(`/api/upload/${activeTargetUser}/${activeFolderType}`, { method: 'POST', body: formData })
        .then(async res => {
            if(!res.ok) {
                let errData = await res.json();
                throw new Error(errData.error || "Transmission rejected.");
            }
            return res.json();
        })
        .then(() => {
            loader.style.display = 'none';
            if(activeTargetUser && activeFolderType) {
                loadFolder(activeFolderType);
            }
        })
        .catch(err => {
            loader.style.display = 'none';
            alert("⚠️ " + err.message);
        });
}

function deleteTargetFile(filename) {
    if(!confirm(`Purge ${filename} permanently?`)) return;
    let formData = new FormData();
    formData.append('target_user', activeTargetUser);
    formData.append('folder_type', activeFolderType);
    formData.append('filename', filename);
    fetch('/api/delete_file', { method: 'POST', body: formData })
        .then(res => res.json()).then(data => { if(data.status === 'deleted') loadFolder(activeFolderType); });
}

function deleteUserAccount(username) {
    if(!confirm(`Delete entry: ${username}?`)) return;
    fetch(`/admin/delete_user/${username}`, { method: 'POST' })
        .then(res => res.json()).then(data => { if(data.status === 'user_removed') document.getElementById(`row-user-${username}`).remove(); });
}

function commitPasswordUpdate() {
    let pass = document.getElementById('newPasswordInput').value; 
    if(!pass) return alert("Field cannot be blank.");
    let formData = new FormData(); formData.append('new_password', pass);
    fetch('/api/change_password', { method: 'POST', body: formData }).then(res => res.json()).then(data => {
        if(data.status === 'success') { alert("Password updated successfully."); closeWindow('settingsWindow'); document.getElementById('newPasswordInput').value = ""; }
    });
}

function updateLiveDiskQuotaVisuals() {
    let fill = document.getElementById('adminQuotaFillBar');
    let logger = document.getElementById('adminQuotaTextLogger');
    if(!fill || !logger) return;
    let usedMb = parseFloat(document.body.getAttribute('data-used-mb') || '0');
    let maxQuotaMb = 250.0;
    let pct = Math.min((usedMb / maxQuotaMb) * 100, 100);
    fill.style.width = pct + '%';
    logger.innerText = `${usedMb} MB used out of ${maxQuotaMb} MB (${Math.round(pct * 100) / 100}%)`;
}

const dropZone = document.getElementById('dropZoneContainer');
if (dropZone) {
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evName => {
        dropZone.addEventListener(evName, (e) => { e.preventDefault(); e.stopPropagation(); }, false);
    });
    dropZone.addEventListener('drop', (e) => {
        if (!activeFolderType) return;
        let files = e.dataTransfer.files;
        if (files.length === 0) return;
        let remark = prompt(`Enter custom description remark for [ ${files[0].name} ] :`, "Uploaded via Drag-and-Drop.");
        if (remark === null) return;
        executeAsynchronousUploadPipeline(files[0], remark);
    }, false);
}
