/**
 * create_map_template.jsx — vytvoří nový AI dokument jako šablonu pro mapu/infografiku.
 *
 * Parametry se vkládají jako string-replace před spuštěním:
 *   %%WIDTH%% — šířka dokumentu v pt
 *   %%HEIGHT%% — výška dokumentu v pt
 *   %%SAVE_PATH%% — cesta k uložení .ai souboru (forward slashes)
 *   %%BLEED%% — velikost bleedu v pt (default 0)
 *   %%LABEL_TEXT%% — volitelný label/popisek
 *   %%FONT_FAMILY%% — font pro labely (default "MinionPro-Regular")
 *
 * Vrací JSON.stringify({path, width, height}).
 */

(function () {
    var docWidth = %%WIDTH%%;
    var docHeight = %%HEIGHT%%;
    var savePath = "%%SAVE_PATH%%";
    var bleed = %%BLEED%%;
    var labelText = "%%LABEL_TEXT%%";
    var fontFamily = "%%FONT_FAMILY%%";

    try {
        // Nový dokument
        var preset = new DocumentPreset();
        preset.width = docWidth;
        preset.height = docHeight;
        preset.units = RulerUnits.Points;
        preset.colorMode = DocumentColorSpace.CMYK;

        var doc = app.documents.addDocument(
            DocumentColorSpace.CMYK,
            preset
        );
        doc.name = "MapTemplate";

        // Přidat bleed guides (pokud bleed > 0)
        if (bleed > 0) {
            var guideLayer = doc.layers.add();
            guideLayer.name = "Guides";

            // Crop area obdélník (bleed boundary)
            var cropRect = guideLayer.pathItems.rectangle(
                docHeight + bleed,  // top
                -bleed,             // left
                docWidth + 2 * bleed,
                docHeight + 2 * bleed
            );
            cropRect.stroked = true;
            cropRect.filled = false;
            var cyan = new CMYKColor();
            cyan.cyan = 100;
            cyan.magenta = 0;
            cyan.yellow = 0;
            cyan.black = 0;
            cropRect.strokeColor = cyan;
            cropRect.strokeWidth = 0.5;

            // Trim area obdélník
            var trimRect = guideLayer.pathItems.rectangle(
                docHeight,  // top
                0,          // left
                docWidth,
                docHeight
            );
            trimRect.stroked = true;
            trimRect.filled = false;
            var magenta = new CMYKColor();
            magenta.cyan = 0;
            magenta.magenta = 100;
            magenta.yellow = 0;
            magenta.black = 0;
            trimRect.strokeColor = magenta;
            trimRect.strokeWidth = 0.25;

            guideLayer.locked = true;
        }

        // Hlavní vrstva pro obsah
        var contentLayer;
        if (doc.layers.length > 0) {
            contentLayer = doc.layers[0];
            if (contentLayer.name === "Guides") {
                contentLayer = doc.layers.add();
            }
        } else {
            contentLayer = doc.layers.add();
        }
        contentLayer.name = "Map Content";

        // Label text frame (pokud je zadán)
        if (labelText && labelText !== "") {
            var labelLayer = doc.layers.add();
            labelLayer.name = "Labels";

            var tf = labelLayer.textFrames.add();
            tf.contents = labelText;
            tf.position = [10, docHeight - 10];
            tf.textRange.size = 8;

            // Zkusit nastavit font
            try {
                tf.textRange.textFont = app.textFonts.getByName(fontFamily);
            } catch (e) {
                // Font nenalezen — ponechat default
            }

            var labelColor = new CMYKColor();
            labelColor.cyan = 0;
            labelColor.magenta = 0;
            labelColor.yellow = 0;
            labelColor.black = 50;
            tf.textRange.fillColor = labelColor;
        }

        // Uložit jako .ai
        var aiFile = new File(savePath);
        var saveOpts = new IllustratorSaveOptions();
        saveOpts.compatibility = Compatibility.ILLUSTRATOR17; // CC
        saveOpts.pdfCompatible = true;
        doc.saveAs(aiFile, saveOpts);

        // Výstup
        var result = {
            path: savePath,
            width: docWidth,
            height: docHeight,
            bleed: bleed,
            success: true
        };
        return JSON.stringify(result);

    } catch (err) {
        return JSON.stringify({
            success: false,
            error: err.toString()
        });
    }
})();
