(function (cs) {

    "use strict";


    var scanImages = [];

    function createImageObjects(imageId, image_data) {
        var volume = new Uint16Array(image_data);
        var width = scan_md.width;
        var height = scan_md.height;

        var sliceSize = width * height;
        for (var i = 0; i < scan_md.slices; i++) {
            var sliceVolume = volume.subarray(i * sliceSize, (i * sliceSize) + sliceSize);
            createImageObject("aidoc://" + scan_md.uid + "/" + i,i,sliceVolume);
        }
    }

    function createImageObject(imageId, slice, slice_volume) {

        var width = scan_md.width;
        var height = scan_md.height;


        scanImages[slice] = {
            imageId: imageId,
            minPixelValue: -1000,
            maxPixelValue: 4000,
            slope: 1.0,
            intercept: 0,
            windowCenter: 70,
            windowWidth: 50,
            render: cs.renderGrayscaleImage,
            getPixelData: function () {
                return slice_volume;
            },
            rows: height,
            columns: width,
            height: height,
            width: width,
            color: false,
            columnPixelSpacing: .8984375,
            rowPixelSpacing: .8984375,
            sizeInBytes: width * height * 2
        };
    }


    function loadImage(imageId) {

        var parts = imageId.split('/');

        var uid = parts[2];

        var slice = 0;
        if (parts.length > 3)
            slice = parseInt(parts[3]);


        // create a deferred object
        var deferred = $.Deferred();

        if (scanImages[slice]) {
            // deferred.resolve(scanImages[slice]);
            return $.when(scanImages[slice]);
        }

        // Make the request for the DICOM data
        var oReq = new XMLHttpRequest();
        oReq.open("get", "../get-scan/" + uid, true);
        oReq.responseType = "arraybuffer";
        oReq.onreadystatechange = function (oEvent) {
            if (oReq.readyState === 4) {
                if (oReq.status == 200) {
                    // request succeeded, create an image object and resolve the deferred
                    // Code to parse the response and return an image object omitted.....
                    // var image = createImageObject(imageId, slice, oReq.response);
                    createImageObjects(imageId,  oReq.response);
                    // return the image object by resolving the deferred
                    deferred.resolve(scanImages[slice]);
                }
                else {
                    // an error occurred, return an object describing the error by rejecting
                    // the deferred
                    deferred.reject({error: oReq.statusText});
                }
            }
        };
        oReq.send();

        // return the pending deferred object to cornerstone so it can setup callbacks to be
        // invoked asynchronously for the success/resolve and failure/reject scenarios.
        return deferred;
    }

    // register our imageLoader plugin with cornerstone
    // cs.registerImageLoader('example', getExampleImage);
    cs.registerImageLoader('aidoc', loadImage);

}(cornerstone));