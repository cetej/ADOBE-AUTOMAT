// ExtendScript pro extrakci vsech textovych ramcu z aktivniho dokumentu v Illustratoru.
// Vraci JSON array s vrstvami a jejich texty.
// Spousteno pres CEP executeExtendScript — vysledek musi byt return JSON.stringify(result).
// DULEZITE: layer.textFrames je hluboka kolekce (zahrnuje podvrstvy).
// Proto filtrujeme jen PRIME potomky dane vrstvy — podvrstvy se zpracuji rekurzivne.

var doc = app.activeDocument;
var result = [];

// Zjisti, zda textFrame patri primo do dane vrstvy (ne do podvrstvy).
// Prochazi parent chain — pokud narazi na jinou Layer driv nez na "layer", patri podvrstve.
function isDirectChild(tf, layer) {
    var p = tf.parent;
    while (p) {
        if (p === layer) return true;
        if (p.typename === "Layer" && p !== layer) return false;
        p = p.parent;
    }
    return false;
}

function processLayer(layer, depth) {
    var layerTexts = [];
    var directIdx = 0;

    for (var j = 0; j < layer.textFrames.length; j++) {
        var tf = layer.textFrames[j];

        // Preskocit textFrames z podvrstev — budou zpracovany rekurzivne
        if (!isDirectChild(tf, layer)) continue;

        var bounds = tf.geometricBounds; // [left, top, right, bottom]
        var fs = 0;
        try {
            fs = tf.textRange.characterAttributes.size;
        } catch(e) {
            fs = 0;
        }

        layerTexts.push({
            index: directIdx,
            contents: tf.contents,
            position: [
                Math.round(bounds[0] * 100) / 100,
                Math.round(-bounds[1] * 100) / 100
            ],
            width: Math.round((bounds[2] - bounds[0]) * 100) / 100,
            height: Math.round((-bounds[3] + bounds[1]) * 100) / 100,
            kind: tf.kind.toString(),
            fontSize: Math.round(fs * 100) / 100
        });
        directIdx++;
    }

    if (layerTexts.length > 0) {
        result.push({
            layerName: layer.name,
            layerId: layer.absoluteZOrderPosition,
            texts: layerTexts
        });
    }

    // Rekurzivne zpracovat podvrstvy
    for (var k = 0; k < layer.layers.length; k++) {
        processLayer(layer.layers[k], depth + 1);
    }
}

for (var i = 0; i < doc.layers.length; i++) {
    processLayer(doc.layers[i], 0);
}

// Vratit vcetne info o dokumentu (nazev, cesta)
var docInfo = {
    name: doc.name,
    path: doc.fullName ? doc.fullName.fsName.replace(/\\/g, '/') : ''
};

return JSON.stringify({layers: result, document: docInfo});
