// ExtendScript pro zapis prelozenych textu zpet do aktivniho dokumentu v Illustratoru.
// Vstup: JSON pole [[layerName, layerId, textIndex, newText], ...]
//   layerId = -1 znamena "najdi podle jmena" (neni duplicitni)
//   layerId >= 0 znamena "najdi vrstvu se jmenem a absoluteZOrderPosition == layerId"
// Spousteno pres CEP executeExtendScript — vysledek musi byt return JSON.stringify(result).
// DULEZITE: \r pro zalomeni radku (ne \n).
// DULEZITE: layer.textFrames je hluboka kolekce — pouzivame isDirectChild() pro konzistenci s extrakci.

var doc = app.activeDocument;
var changed = 0;
var errors = [];

// %%TRANSLATIONS%% bude nahrazeno Python servisem
var translations = %%TRANSLATIONS%%;

// Cache vrstev — klic: "name" nebo "name#zorder"
var layersByName = {};  // name -> [layer, layer, ...]
var layersByNameId = {}; // "name#zorder" -> layer

function cacheLayer(layer) {
    var n = layer.name;
    if (!layersByName[n]) layersByName[n] = [];
    layersByName[n].push(layer);
    layersByNameId[n + "#" + layer.absoluteZOrderPosition] = layer;
    for (var k = 0; k < layer.layers.length; k++) {
        cacheLayer(layer.layers[k]);
    }
}

for (var i = 0; i < doc.layers.length; i++) {
    cacheLayer(doc.layers[i]);
}

// Zjisti, zda textFrame patri primo do dane vrstvy (ne do podvrstvy).
function isDirectChild(tf, layer) {
    var p = tf.parent;
    while (p) {
        if (p === layer) return true;
        if (p.typename === "Layer" && p !== layer) return false;
        p = p.parent;
    }
    return false;
}

// Najde N-ty primy textFrame ve vrstve (konzistentni s extrakci).
function getDirectTextFrame(layer, index) {
    var directIdx = 0;
    for (var j = 0; j < layer.textFrames.length; j++) {
        var tf = layer.textFrames[j];
        if (!isDirectChild(tf, layer)) continue;
        if (directIdx === index) return tf;
        directIdx++;
    }
    return null;
}

// Spocita prime textFrames ve vrstve.
function countDirectTextFrames(layer) {
    var count = 0;
    for (var j = 0; j < layer.textFrames.length; j++) {
        if (isDirectChild(layer.textFrames[j], layer)) count++;
    }
    return count;
}

// Zpracovani prekladu
for (var t = 0; t < translations.length; t++) {
    var layerName = translations[t][0];
    var layerId = translations[t][1];
    var textIndex = translations[t][2];
    var newText = translations[t][3];

    // Najdi vrstvu — pokud mame layerId, hledej presne
    var layer = null;
    if (layerId >= 0) {
        layer = layersByNameId[layerName + "#" + layerId];
    }
    // Fallback na jmeno (prvni nalezena)
    if (!layer && layersByName[layerName] && layersByName[layerName].length > 0) {
        layer = layersByName[layerName][0];
    }

    if (!layer) {
        errors.push({layer: layerName, index: textIndex, error: "Layer not found"});
        continue;
    }

    // Najdi primy textFrame podle indexu (konzistentni s extrakci)
    var tf = getDirectTextFrame(layer, textIndex);
    if (!tf) {
        var directCount = countDirectTextFrames(layer);
        errors.push({layer: layerName, index: textIndex, error: "Text index out of range (" + directCount + " direct frames)"});
        continue;
    }

    try {
        // Odemknout a zviditelnit vrstvu (a rodicovske) pokud je zamcena/skryta
        var lockedLayers = [];
        var hiddenLayers = [];
        var lyr = layer;
        while (lyr) {
            if (lyr.locked) {
                lockedLayers.push(lyr);
                lyr.locked = false;
            }
            if (!lyr.visible) {
                hiddenLayers.push(lyr);
                lyr.visible = true;
            }
            lyr = lyr.parent && lyr.parent.typename === "Layer" ? lyr.parent : null;
        }

        tf.contents = newText;
        changed++;

        // Obnovit stav — zamknout a skryt zpet
        for (var r = 0; r < lockedLayers.length; r++) {
            lockedLayers[r].locked = true;
        }
        for (var h = 0; h < hiddenLayers.length; h++) {
            hiddenLayers[h].visible = false;
        }
    } catch(e) {
        errors.push({layer: layerName, index: textIndex, error: e.toString()});
        // Obnovit stav i pri chybe
        for (var r2 = 0; r2 < lockedLayers.length; r2++) {
            try { lockedLayers[r2].locked = true; } catch(ignore) {}
        }
        for (var h2 = 0; h2 < hiddenLayers.length; h2++) {
            try { hiddenLayers[h2].visible = false; } catch(ignore) {}
        }
    }
}

return JSON.stringify({changed: changed, total: translations.length, errors: errors});
