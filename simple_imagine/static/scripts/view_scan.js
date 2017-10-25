var app = new Vue({
  el: '#app',
  data: {
    message: 'Hello Vue!'
  }
})

loadScan = function () {


    cornerstone.enable(element);
    cornerstone.loadImage(imageIds[stack.currentImageIdIndex]).then(function (image) {
        cornerstone.addLayer(element, image);

        cornerstone.updateImage(element);

        cornerstoneTools.addStackStateManager(element, ['stack']);
        cornerstoneTools.addToolState(element, 'stack', stack);

        cornerstoneTools.mouseInput.enable(element);
        cornerstoneTools.mouseWheelInput.enable(element);
        cornerstoneTools.stackScrollWheel.activate(element);
        cornerstoneTools.pan.activate(element, 2);
        cornerstoneTools.zoom.activate(element, 4);

        var enabledElement = cornerstone.getEnabledElement(element);

        $.get("/get-rois/" + scan_md.uid + "/" + stack.currentImageIdIndex, function (data) {
            console.log(data);

            for (i = 0; i < data.length; i++) {
                var roi = data[i];

                drawROI(enabledElement, roi['x'], roi['y'], roi['w'], roi['h'], roi['color']);
            }

        });
    });

    refresh_roi_groups(scan_md.uid);

}

//Register for mouse events
$('#dicomImage').on("CornerstoneToolsMouseUp", function (e, eventData) {

    x = eventData.startPoints.canvas.x;
    y = eventData.startPoints.canvas.y;
    w = eventData.currentPoints.canvas.x - eventData.startPoints.canvas.x;
    h = eventData.currentPoints.canvas.y - eventData.startPoints.canvas.y;
    var color = document.getElementById('drawColor').value;

    var enabledElement = cornerstone.getEnabledElement(eventData.element);


    //save the ROI by posting to the server
    var roi = {
        'scan_id': scan_md.uid,
        'x': x,
        'y': y,
        'w': w,
        'h': h,
        'color': color,
        'image_index': stack.currentImageIdIndex
    };


    $.post("/add-roi", JSON.stringify(roi), function (roi) {

        drawROI(enabledElement, roi['x'], roi['y'], roi['w'], roi['h'], roi['color']);
        refresh_roi_groups(scan_md.uid);
    });

});




$('#dicomImage').on("CornerstoneImageRendered", function (e, eventData) {

    var enabledElement = cornerstone.getEnabledElement(eventData.element);

    $.get("/get-rois/" + scan_md.uid + "/" + stack.currentImageIdIndex, function (data) {

        for (var i = 0; i < data.length; i++) {
            var roi = data[i];

            drawROI(enabledElement, roi['x'], roi['y'], roi['w'], roi['h'], roi['color']);
        }
    });
});

// Handles the event of roi table row selection
$("#roiTable").on('click', 'td', function (e) {

    $('.selected').removeClass('selected');
    $(this).parents('tr').addClass('selected');
    selectedROI = $(this).attr('id');
});


// Handles the event of erasing an ROI group
$('#erase').click(function () {

    if (selectedROI != null) {
        var to_delete = {'scan_id': scan_md.uid, 'id': selectedROI};
        $.post("/delete-roi", JSON.stringify(to_delete), function (data) {

            // re renders the image
            cornerstone.enable(element);

            refresh_roi_groups(scan_md.uid);
            selectedROI = null;
        });
    }
});

// Handles the event of erasing an ROI group
$('#save').click(function () {

    var to_save = {'scan_id': scan_md.uid};
    $.post("/save", JSON.stringify(to_save));

});

refresh_roi_groups = function (scan_id) {
    $.get("/get-roi-groups/" + scan_id, function (data) {
        var roi_groups = data;


        $("#roiTable tbody").html("");

        for (var i = 0; i < roi_groups.length; i++) {
            var roi = roi_groups[i];

            var color = roi["color"];
            var roi_row = '<tr style="cursor:pointer"><td id="' + color + '" bgcolor="' + color + '">'
                + roi["label"] + ' ' + roi["min_slice"] + ':' + roi["max_slice"] + '</td></tr>';
            $("#roiTable tbody").append(roi_row);

        }
    });
}

function hexToRGB(hex, alpha) {
    var r = parseInt(hex.slice(1, 3), 16),
        g = parseInt(hex.slice(3, 5), 16),
        b = parseInt(hex.slice(5, 7), 16);

    if (alpha) {
        return "rgba(" + r + ", " + g + ", " + b + ", " + alpha + ")";
    } else {
        return "rgb(" + r + ", " + g + ", " + b + ")";
    }
}


// Draws the ROI polygon on instance
function drawROI(enabledElement, x, y, w, h, color) {

    var context = enabledElement.canvas.getContext('2d');
    context.save();

    context.fillStyle = hexToRGB(color, 0.5);

    context.fillRect(x, y, w, h);

    context.restore();
}


loadScan();



