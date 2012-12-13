from collections import OrderedDict
from functools import partial

import cairo

import segeParser as sp
DASH_PATTERN = [6, 4]
boring_style = {"font-face": ("Sans",
                              cairo.FONT_SLANT_NORMAL,
                              cairo.FONT_WEIGHT_NORMAL),
                "font-size": (10),
                "line-spacing": 1,
                "text-color": (0.0, 0.0, 0.0),
                "background-color": (1.0, 1.0, 1.0),
                "line-width": 1,
                "line-type": "regualr",
                "wait-height": 23,
                "color": (0.0, 0.0, 0.0),
                "activity-box-width": 10,
                "page.padding": (0, 0, 5, 0),
                "entity.padding": (5, 10, 23, 10),
                "entity.margin": (5, 10, 5, 10),
                "lifeline.line-type": "dash",
                "block.padding": (5, 10, 5, 10),
                "block.margin": (5, 10, 5, 10),
                "block.seperator-style": "dash",
                #"block.background-color" : (0.95, 0.95, 0.95),
                "note.padding": (10, 10, 10, 10),
                "note.margin": (10, 10, 10, 10),
                "note.background-color": (0.9, 0.9, 0.5),
                "message.padding": (5, 0, 5, 0),
                "message.margin": (0, 5, 0, 5),
                "message.arrowhead-size": (12.0, 12.0),
                "message.arrowhead-fill-color": (0.0, 0.0, 0.0),
                "message.call.arrowhead-type": "filled",
                "message.send.arrowhead-type": "line",
                "message.respond.arrowhead-type": "line",
                "message.respond.line-type": "dash"}


def compileSource(fname):
    with open(fname, "r") as f:
        ast = sp.parse(f.read())

    return _SegeCompiler().compile(ast)


class _SegeCompiler(object):
    def __init__(self):
        self.entities = OrderedDict()
        self.layers = [[], [], []]
        self._bottom = 0
        self._extraRightPadding = 0

    def getStyle(self, *rawargs):
        selector = ".".join(rawargs)
        args = selector.split(".")
        for i in range(len(args)):
            try:
                key = ".".join(args[:-(i + 1)] + [args[-1]])
                #print "trying", key
                return self._style[key]
            except KeyError:
                pass
        raise KeyError(selector)

    def processOperation(self, op):
        try:
            opName = op.__class__.__name__
            func = getattr(self, "process%s" % opName)
        except:
            print "Skipping unknown operation %s" % opName
            return

        #print "proceesing operation %s" % opName
        return func(op)

    def getFontExtents(self, stylePrefix):
        pfx = stylePrefix
        self.ctx.select_font_face(*self.getStyle(pfx, "font-face"))
        self.ctx.set_font_size(self.getStyle(pfx, "font-size"))
        return self.ctx.font_extents()

    def getTotalSize(self):
        lastEnt = self.entities.keys()[-1]
        center = self.getEntityBoxLocation(lastEnt)
        width = self.getEntityBoxSize(lastEnt)[0]
        totalWidth = center + (width / 2) + self._extraRightPadding
        pb = self.getStyle("page.padding")[2]
        return totalWidth, self._bottom + pb

    def getTextSize(self, text, style):
        lines = text.splitlines()
        (ascent, descent, height,
         max_x_advance, max_y_advance) = self.getFontExtents(style)
        totalHeight = 0
        totalWidth = 0
        for line in lines:
            if line.endswith("\n"):
                line = line[:-1]
            (x_bearing, y_bearing, width, height,
             x_advance, y_advance) = self.getTextExtents(line, style)
            totalWidth = max(totalWidth, width)
            totalHeight -= y_bearing - descent
        lineSpaceing = self.getStyle(style, "line-spacing")
        return (totalWidth, totalHeight + lineSpaceing * (len(lines) - 1))

    def getHeaderHeight(self):
        # TODO : Change to getEntityBoxSize()
        pt = self.getStyle("page", "padding")[0]
        return self.getBoxedTextSize("TEXT", "entity")[1] + pt

    def compile(self, ast, style=boring_style):
        self._style = style
        target = cairo.ImageSurface(cairo.FORMAT_RGB24, 1, 1)
        self.ctx = cairo.Context(target)
        self._bottom = self.getHeaderHeight()
        self.processOperation(ast)

        target = cairo.ImageSurface(cairo.FORMAT_RGB24,
                                    *[int(arg) for arg in self.getTotalSize()])
        ctx = self.ctx = cairo.Context(target)
        ctx.set_source_rgb(*self.getStyle("page.background-color"))
        ctx.rectangle(0, 0, *self.getTotalSize())
        ctx.fill()
        for drawOp in self.layers[0]:
            drawOp()
        self.drawBase()
        for layer in self.layers[1:]:
            for drawOp in layer:
                drawOp()

        target.flush()
        return target

    def drawBase(self):
        for ent in self.entities:
            self.drawEntityBox(ent)
            self.drawLifeLine(ent)

    def drawEntityBox(self, ent):
        center = self.getEntityBoxLocation(ent)
        width = self.getEntityBoxSize(ent)[0]
        #TODO : implement left\right page padding
        pt = self.getStyle("page", "padding")[0]
        self.drawBoxedText((center - width / 2), pt, ent.name, "entity")

    def drawLifeLine(self, ent):
        center = self.getEntityBoxLocation(ent)
        height = self.getEntityBoxSize(ent)[1]
        pt, pr, pb, pl = self.getStyle("entity", "padding")
        self.drawLine(center, height - pb, center, self._bottom, "lifeline")
        actBoxWidth = self.getStyle("activity-box-width")
        for (actStart, actStop) in self.entities[ent]["activity"]:
            if actStop is None:
                actStop == self._bottom
            self.drawRectangle(center - actBoxWidth / 2, actStart,
                               actBoxWidth, actStop - actStart, "activity-box")

    def drawLine(self, x, y, x2, y2, stylePrefix):
        self.ctx.set_source_rgb(*self.getStyle(stylePrefix, "color"))
        self.ctx.set_line_width(self.getStyle(stylePrefix, "line-width"))
        if self.getStyle(stylePrefix, "line-type") == "dash":
            self.ctx.set_dash(DASH_PATTERN)
        self.ctx.move_to(x, y)
        self.ctx.line_to(x2, y2)
        self.ctx.stroke()
        self.ctx.set_dash([])

    def processSequence(self, seq):
        for op in seq.operations:
            self.processOperation(op)

    def processNote(self, op):
        #TODO : implement left\right of
        #TODO : handle activated lifelines better
        style = "note.%s" % op.position
        width, height = self.getBoxedTextSize(op.text, style)
        ents = self.entities.keys()
        myIndex = ents.index(op.entity)
        if myIndex == 0:
            pent = None
        else:
            pent = ents[myIndex - 1]
        self.adjustLifeLineDistance(pent, op.entity, width / 2)
        try:
            nent = ents[myIndex + 1]
        except IndexError:
            padding = (width / 2) - (self.getEntityBoxSize(pent)[0])
            self._extraRightPadding = max(self._extraRightPadding, padding)
        else:
            self.adjustLifeLineDistance(op.entity, nent, width / 2)
        self.layers[1].append(partial(self.drawNote, self._bottom, op.entity,
                                      op.position, op.text))
        self._bottom += height

    def drawNote(self, top, entity, position, text):
        style = "note.%s" % position
        width, height = self.getBoxedTextSize(text, style)
        center = self.getEntityBoxLocation(entity)
        self.drawBoxedText(center - width / 2, top, text, style)

    def processWait(self, op):
        self._bottom += self.getStyle("wait-height")

    def processSetActivationState(self, op):
        for ent in op.entityList:
            activity = self.entities[ent]["activity"]
            if (op.activationState and
                    (len(activity) == 0 or activity[-1][1] is not None)):
                activity.append([self._bottom, None])
                self.entities[ent]["active"] = True

            if (not op.activationState and
                    (len(activity) > 0 and activity[-1][1] is None)):
                activity[-1][1] = self._bottom
                self.entities[ent]["active"] = False

    def getBoxedTextSize(self, text, stylePrefix):
        pfx = stylePrefix
        pt, pr, pb, pl = self.getStyle(pfx, "padding")
        mt, mr, mb, ml = self.getStyle(pfx, "margin")
        width, height = self.getTextSize(text, pfx)
        return (pr + mr + width + ml + pl, pt + mt + height + mb + pb)

    def getEntityBoxSize(self, entity):
        return self.getBoxedTextSize(entity.name, "entity")

    def processDeclareEntity(self, op):
        if len(self.entities) == 0:
            prevEnt = None
            offset = 0
        else:
            prevEnt = self.entities.keys()[-1]
            offset = self.getEntityBoxSize(prevEnt)[0] / 2
        offset += self.getEntityBoxSize(op.entity)[0] / 2

        self.entities[op.entity] = {"locationConstraint": (prevEnt, offset),
                                    "active": False,
                                    "activity": []}

    def getEntityBoxLocation(self, ent):
        relEnt, offset = self.entities[ent]["locationConstraint"]
        if relEnt is None:
            return offset
        else:
            return offset + self.getEntityBoxLocation(relEnt)

    def adjustLifeLineDistance(self, entA, entB, width):
        if entA is None:
            lifelineA = 0
        else:
            lifelineA = self.getEntityBoxLocation(entA)
        lifelineB = self.getEntityBoxLocation(entB)
        dist = lifelineB - lifelineA
        if dist < 0:
            tmp = entB
            entB = entA
            entA = tmp
            dist = lifelineA - lifelineB

        if dist < width:
            self.entities[entB]["locationConstraint"] = (entA, width)

    def processAlt(self, alt):
        style = "block.alt"
        totalWidth = 0
        for condition in alt.conditions:
            width, height = self.getBlockMinSize("alt", condition.condition,
                                                 style)
            totalWidth = max(totalWidth, width)

        self.adjustLifeLineDistance(None, self.entities.keys()[0], totalWidth)

        pt, pr, pb, pl = self.getStyle(style, "padding")
        mt, mr, mb, ml = self.getStyle(style, "margin")
        mytop = top = self._bottom
        firstOp = alt.conditions[0]
        self._bottom += pt + mt
        self.processOperation(firstOp.sequence)
        height = self.getBlockMinSize("alt", firstOp.condition, style)[1]
        self._bottom = max(self._bottom, top + height)
        for op in alt.conditions[1:]:
            self.layers[2].append(partial(self.drawBlockSeperator,
                                          self._bottom,
                                          "[%s]" % op.condition, style))
            mytop = self._bottom
            self._bottom += pt + mt
            self.processOperation(op.sequence)
            height = self.getBlockSeperatorHeight(op.condition, style)
            self._bottom = max(self._bottom, mytop + height)
        self._bottom += pb + mb
        bottom = self._bottom

        self.layers[0].append(partial(self.drawBlockBackground, top, bottom,
                                      style))
        self.layers[2].append(partial(self.drawBlockFrame,
                                      top,
                                      bottom,
                                      "alt",
                                      "[%s]" % alt.conditions[0].condition,
                                      style))

    def getBlockSeperatorHeight(self, text, style):
        mt, mr, mb, ml = self.getStyle(style, "margin")
        return self.getTextSize(text, style)[1] + mt

    def drawBlockSeperator(self, pos, text, style):
        ppt, ppr, ppb, ppl = self.getStyle("page", "padding")
        pt, pr, pb, pl = self.getStyle(style, "padding")
        mt, mr, mb, ml = self.getStyle(style, "margin")
        self.ctx.set_source_rgb(*self.getStyle(style, "color"))

        width = self.getTotalSize()[0]
        width -= ppl + pl + ppr + pr

        if self.getStyle(style, "seperator-style") == "dash":
            self.ctx.set_dash(DASH_PATTERN)
        self.ctx.move_to(ppl + pl, pos)
        self.ctx.rel_line_to(width, 0)
        self.ctx.stroke()
        self.ctx.set_dash([])
        self.drawText(ppl + pl + ml, pos + mt, text, style)

    def processLoop(self, op):
        self.processBlock("loop", "[%s]" % op.condition, op, "block.loop")

    def processOpt(self, op):
        self.processBlock("opt", "[%s]" % op.condition, op, "block.opt")

    def processMessage(self, msg):
        srcActive = self.entities[msg.src]["active"]
        dstActive = self.entities[msg.dst]["active"]
        self.layers[1].append(partial(self.drawMessage, msg, self._bottom,
                                      srcActive, dstActive))

        width, height = self.getMessageBoxSize(msg)
        self._bottom += height
        self.adjustLifeLineDistance(msg.src, msg.dst, width)

    def processBlock(self, title, text, op, style):
        width, height = self.getBlockMinSize(title, text, style)
        self.adjustLifeLineDistance(None, self.entities.keys()[0], width)

        pt, pr, pb, pl = self.getStyle(style, "padding")
        mt, mr, mb, ml = self.getStyle(style, "margin")
        top = self._bottom
        self._bottom += pt + mt
        self.processOperation(op.sequence)
        self._bottom += pb + mb
        self._bottom = bottom = max(self._bottom, top + height)

        self.layers[0].append(partial(self.drawBlockBackground, top, bottom,
                                      style))
        self.layers[2].append(partial(self.drawBlockFrame, top, bottom, title,
                                      text, style))

    def drawBlockBackground(self, top, bottom, style):
        ppt, ppr, ppb, ppl = self.getStyle("page", "padding")
        pt, pr, pb, pl = self.getStyle(style, "padding")
        mt, mr, mb, ml = self.getStyle(style, "margin")
        width = self.getTotalSize()[0]
        self.ctx.set_source_rgb(*self.getStyle(style, "background-color"))
        width -= ppl + pl + ppr + pr
        self.ctx.rectangle(ppl + pl, top + pt, width, bottom - top - pb - pt)
        self.ctx.fill()

    def drawBlockFrame(self, top, bottom, title, text, style):
        ppt, ppr, ppb, ppl = self.getStyle("page", "padding")
        pt, pr, pb, pl = self.getStyle(style, "padding")
        mt, mr, mb, ml = self.getStyle(style, "margin")
        self.ctx.set_source_rgb(*self.getStyle(style, "color"))

        titleWidth, titleHeight = self.getTextSize(title, style)
        textWidth, textHeight = self.getTextSize(text, style)

        width = self.getTotalSize()[0]
        width -= ppl + pl + ppr + pr

        self.ctx.rectangle(ppl + pl, top + pt, width, bottom - top - pb - pt)
        self.ctx.stroke()

        self.drawText(ppl + pl + ml, top + pt + mt, title, style)
        self.drawText(ppl + pl + ml, top + pt + mt + titleHeight + mb + mt,
                      text, style)

        self.ctx.set_source_rgb(*self.getStyle(style, "color"))
        self.ctx.move_to(ppl + pl, top + pt + mt + titleHeight + mb)
        self.ctx.line_to(ppl + pl + mr + titleWidth, top + pt + mt +
                         titleHeight + mb)
        self.ctx.line_to(ppl + pl + mr + titleWidth + ml, top + pt + mt +
                         titleHeight)
        self.ctx.line_to(ppl + pl + mr + titleWidth + ml, top + pt)
        self.ctx.stroke()

    def getBlockMinSize(self, title, text, style):
        pt, pr, pb, pl = self.getStyle(style, "padding")
        mt, mr, mb, ml = self.getStyle(style, "margin")
        titleWidth, titleHeight = self.getTextSize(title, style)
        textWidth, textHeight = self.getTextSize(text, style)
        return (pr + mr + max(textWidth, titleWidth) + ml + pl,
                pt + mt + titleHeight + mb + mt + textHeight + mb + pb)

    def getMessageBoxSize(self, msg):
        style = "message.%s" % msg.msgType
        textWidth, textHeight = self.getTextSize(msg.text, style)
        arrowheadWith, arrowheadHeight = self.getStyle(style, "arrowhead-size")
        pt, pr, pb, pl = self.getStyle(style, "padding")
        mt, mr, mb, ml = self.getStyle(style, "margin")
        boxPad = 0
        if self.entities[msg.src]["active"]:
            boxPad += self.getStyle("activity-box-width") / 2

        if self.entities[msg.dst]["active"]:
            boxPad += self.getStyle("activity-box-width") / 2

        return (boxPad + pl + ml + textWidth + arrowheadWith + mr + pr,
                pt + mt + textHeight + (arrowheadHeight / 2) + mb + pb)

    def drawMessage(self, msg, top, srcActive, dstActive):
        srcLoc = self.getEntityBoxLocation(msg.src)
        dstLoc = self.getEntityBoxLocation(msg.dst)
        style = "message.%s" % msg.msgType
        pt, pr, pb, pl = self.getStyle(style, "padding")
        mt, mr, mb, ml = self.getStyle(style, "margin")
        textWidth, textHeight = self.getTextSize(msg.text, style)
        bearing = dstLoc - srcLoc
        bearing = bearing / abs(bearing)
        #TODO : implement horizontal padding
        actBoxPad = self.getStyle("activity-box-width") / 2
        if srcActive:
            srcLoc += bearing * actBoxPad

        if dstActive:
            dstLoc -= bearing * actBoxPad

        if srcLoc < dstLoc:
            textLoc = srcLoc + ml
        else:
            textLoc = srcLoc - textWidth - mr

        self.ctx.set_source_rgb(*self.getStyle(style, "background-color"))
        self.ctx.rectangle(textLoc, top, textWidth, textHeight)
        self.ctx.fill()

        self.drawLine(srcLoc, top + textHeight + mb + mt, dstLoc, top +
                      textHeight + mb + mt, style)
        self.drawText(textLoc, top, msg.text, style)
        self.drawArrowHead(bearing, dstLoc, top + textHeight, style)

    def drawArrowHead(self, bearing, x, y, stylePrefix):
        bearing = (bearing / abs(bearing))
        pfx = stylePrefix
        ahType = self.getStyle(pfx, "arrowhead-type")
        width, height = self.getStyle(pfx, "arrowhead-size")
        self.ctx.set_source_rgb(*self.getStyle(pfx, "color"))
        self.ctx.move_to(x - (width * bearing), y - (height / 2))
        self.ctx.line_to(x, y)
        self.ctx.line_to(x - (width * bearing), y + (height / 2))
        if ahType in ("triangle", "filled"):
            self.ctx.close_path()

        self.ctx.stroke()

        if ahType == "filled":
            self.ctx.set_source_rgb(*self.getStyle(pfx,
                                                   "arrowhead-fill-color"))
            self.ctx.move_to(x - (width * bearing), y - (height / 2))
            self.ctx.line_to(x, y)
            self.ctx.line_to(x - (width * bearing), y + (height / 2))
            self.ctx.fill()

    def getTextExtents(self, text, stylePrefix):
        pfx = stylePrefix
        self.ctx.select_font_face(*self.getStyle("%s.font-face" % pfx))
        self.ctx.set_font_size(self.getStyle("%s.font-size" % pfx))
        return self.ctx.text_extents(text)

    def drawText(self, x, y, text, stylePrefix):
        pfx = stylePrefix
        self.ctx.set_source_rgb(*self.getStyle(pfx, "text-color"))
        self.ctx.select_font_face(*self.getStyle(pfx, "font-face"))
        self.ctx.set_font_size(self.getStyle(pfx, "font-size"))
        lineSpaceing = self.getStyle(pfx, "line-spacing")
        (ascent, descent, height,
         max_x_advance, max_y_advance) = self.getFontExtents(pfx)
        #w, h = self.getTextSize(text, pfx)
        #self.ctx.rectangle(x, y, w, h)
        #self.ctx.stroke()
        for line in text.splitlines():
            #TODO : hanle tabs
            line = line.strip()
            (x_bearing, y_bearing, width, height,
             x_advance, y_advance) = self.getTextExtents(line, pfx)
            #x -= x_bearing
            y -= y_bearing
            self.ctx.move_to(x, y)
            self.ctx.show_text(line)
            y += descent + lineSpaceing

    def drawRectangle(self, x, y, width, height, stylePrefix):
        pfx = stylePrefix
        self.ctx.set_source_rgb(*self.getStyle(pfx, "color"))
        self.ctx.set_line_width(self.getStyle(pfx, "line-width"))
        self.ctx.rectangle(x, y, width, height)
        self.ctx.stroke()
        self.ctx.set_source_rgb(*self.getStyle(pfx, "background-color"))
        self.ctx.rectangle(x, y, width, height)
        self.ctx.fill()

    def drawBoxedText(self, x, y, text, stylePrefix):
        pfx = stylePrefix
        textWidth, textHeight = self.getTextSize(text, pfx)

        pt, pr, pb, pl = self.getStyle(pfx, "padding")
        (margin_top, margin_right,
         margin_bottom, margin_left) = self.getStyle(pfx, "margin")
        rectWidth = margin_right + margin_left + textWidth
        rectHeight = margin_top + margin_bottom + textHeight
        self.drawRectangle(x + pl, y + pt, rectWidth, rectHeight, pfx)

        self.drawText(x + pl + margin_left, y + pt + margin_top, text, pfx)

        return (rectWidth, rectHeight)
