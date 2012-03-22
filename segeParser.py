from collections import OrderedDict

import ply.lex as lex
import ply.yacc as yacc

class Class(object):
    def __init__(self, name, alias):
        self.name = name
        self.alias = alias

    def __repr__(self):
        return "Class(%s, %s)" % (self.name, self.alias)

class Message(object):
    def __init__(self, src, dst, msgType, text):
        self.src = src
        self.dst = dst
        self.msgType = msgType
        self.text = text

    def __repr__(self):
        return "Message(%s, %s, %s, '%s')" % (self.src, self.dst, self.msgType, self.text)

class DeclareEntity(object):
    def __init__(self, entity):
        self.entity = entity

    def __repr__(self):
        return "DeclareEntity(%s)" % self.entity

class Sequence(object):
    def __init__(self,op=None):
        self.operations = []
        if op is not None:
            self.operations.append(op)

    def extend(self, op):
        self.operations.extend(op)

    def append(self, op):
        self.operations.apeend(op)

    def __repr__(self):
        return "Sequence(%s)" % ", ".join([repr(msg) for msg in self.operations])

class SetActivationState(object):
    def __init__(self, entityList, activationState):
        self.entityList = entityList
        self.activationState = activationState

    def __repr__(self):
        return "SetActivationState(%s, %s)" % (self.entityList, self.activationState)

class Destroy(object):
    def __init__(self, entity):
        self.entity = entity

    def __repr__(self):
        return "Destroy(%s)" % (self.entity)

class Loop(object):
    def __init__(self, condition, sequence):
        self.condition = unicode(condition)
        self.sequence = sequence

    def __repr__(self):
        return "Loop(%s, %s)" % (self.condition, self.sequence)

class Alt(object):
    def __init__(self, condition):
        self.conditions = [condition]

    def __repr__(self):
        return "Alt('%s', %s)" % (self.conditions, self.sequence)

class Else(object):
    def __init__(self, condition, sequence):
        self.condition = condition
        self.sequence = sequence

    def __repr__(self):
        return "Else('%s', %s)" % (self.condition, self.sequence)

class Opt(object):
    def __init__(self, condition, sequence):
        self.condition = condition
        self.sequence = sequence

    def __repr__(self):
        return "Opt('%s', %s)" % (self.condition, self.sequence)

class Note(object):
    def __init__(self, position, entity, text):
        self.position = position
        self.entity = entity
        self.text = text

    def __repr__(self):
        return "Note('%s', %s, '%s')" % (self.position, self.entity, self.text)

class Wait(object):
    def __init__(self, count):
        self.count = count

    def __repr__(self):
        return "Wait(%d)" % self.count

class SegeParser(object):
    tokens = [
            "COMMENT",
            "ENTITY",
            "MESSAGE_TYPE",
            "STRING",
            "BLOCK_OPEN",
            "BLOCK_CLOSE",
            "NUMBER",
            "COMMA"
            ]

    t_ignore = " \t"

    keywords = ("activate", "deactivate", "opt", "alt",
                "loop", "else", "destroy", "note" , "over",
                "left", "right", "of", "declare", "as",
                "wait")

    t_COMMA=","
    t_BLOCK_OPEN = "{"
    t_BLOCK_CLOSE = "}"
    def t_ENTITY(self, t):
        r"[a-zA-Z_][a-zA-Z0-9_]*"
        t.type = self.keywords.get(t.value, "ENTITY")
        return t

    def __init__(self):
        self.knownEntities = OrderedDict()
        keywords = self.keywords
        self.keywords = {}
        for word in keywords:
            lexName = word.upper().replace(" ", "_")
            self.tokens.append(lexName)
            self.keywords[word] = lexName
            setattr(self, "t_%s" % lexName, word)

    def t_NUMBER(self, t):
        "\d+"
        t.value = int(t.value)
        return t

    def t_COMMENT(self, t):
        r"\#.*"
        pass

    def t_MESSAGE_TYPE(self, t):
        r"([-~]>|<-)"

        if t.value == "->":
            t.value = "call"
        elif t.value == "~>":
            t.value = "send"
        elif t.value == "<-":
            t.value = "respond"

        return t

    def t_STRING(self, t):
        r'"(\\"|[^"])*"({\d+})?'
        # Take the out the "
        end = -1
        automtrim = 0
        if t.value.endswith("}"):
            end = t.value.find("{")
            automtrim = int(t.value[end + 1:-1])
        txt = t.value[1:end]

        txt = txt.replace(r"\t", "\t")
        txt = txt.replace(r"\"", "\"")
        txt = txt.replace(r"\n", "\n")
        if automtrim > 0:
            i = 0
            while (i + automtrim) < len(txt):
                res = txt.find("\n", i, i + automtrim)
                if res != -1:
                    i = res + 1
                    continue
                j = 0
                extend = 0
                while j < 1:
                    j = txt.rfind(" ", i, i + automtrim + extend)
                    extend += 1
                    if (i + automtrim + extend) == len(txt):
                        j = 0
                        break
                if j == 0:
                    break
                txt = txt[:j] + "\n" + txt[j+1:]
                i = j + 2

        t.value = txt
        return t

    def t_newline(self, t):
        r'\n+'
        t.lexer.lineno += t.value.count("\n")

    def t_error(self, t):
        raise TypeError("Unknown text '%s'" % (t.value,))

    def getEntity(self, alias):
        if alias not in self.knownEntities:
            self.knownEntities[alias] = Class(alias, alias)

        return self.knownEntities[alias]

    def p_sequence(self, p):
        """
        sequence : statement statement
                 | sequence statement
        """
        p[1].extend(p[2].operations)
        p[0] = p[1]

    def p_statement(self, p):
        """
        statement : message
                  | alt
                  | loop
                  | opt
                  | activate
                  | deactivate
                  | destroy
                  | note
                  | declare
                  | wait
        """

        p[0] = Sequence(p[1])

    def p_wait(self, p):
        "wait : WAIT"
        p[0] = Wait(1)

    def p_wait_n(self, p):
        "wait : WAIT NUMBER"
        if p[2] < 1:
            raise yacc.SyntaxEerror("You cannot wait for a negative amount of beats")
        p[0] = Wait(p[2])

    def p_declare_simple(self, p):
        "declare : DECLARE ENTITY"
        self.getEntity(p[2])

    def p_declare_complex(self, p):
        "declare : DECLARE STRING AS ENTITY"
        self.getEntity(p[4]).name = p[2]

    def p_else(self, p):
        "alt : alt ELSE STRING block"
        p[1].conditions.append(Else(p[3], p[4]))
        p[0] = p[1]

    def p_alt(self, p):
        "alt : ALT STRING block"
        p[0] = Alt(Else(p[2], p[3]))

    def p_loop(self, p):
        """
        loop : LOOP STRING block
             | LOOP NUMBER block
        """
        p[0] = Loop(p[2], p[3])

    def p_opt(self, p):
        "opt : OPT STRING block"
        p[0] = Opt(p[2], p[3])

    def p_block(self, p):
        """
        block : BLOCK_OPEN sequence BLOCK_CLOSE
              | BLOCK_OPEN statement BLOCK_CLOSE
        """

        p[0] = p[2]

    def p_empty_block(self, p):
        "block : BLOCK_OPEN BLOCK_CLOSE"
        return Sequence()


    def p_message(self, p):
        """
        message : ENTITY MESSAGE_TYPE ENTITY STRING
        """
        src = self.getEntity(p[1])
        dst = self.getEntity(p[3])
        msgType = p[2]
        text = p[4]

        if msgType in ["respond"]:
            tmp = src
            src = dst
            dst = tmp

        p[0] = Message(src, dst, msgType, text)

    def p_activate(self, p):
        "activate : ACTIVATE ENTITY"
        p[0] = SetActivationState([self.getEntity(p[2])], True)

    def p_activate_list(self, p):
        "activate : ACTIVATE entity_list"
        p[0] = SetActivationState([self.getEntity(ent) for ent in p[2]], True)

    def p_entity_list(self, p):
        "entity_list : ENTITY COMMA ENTITY"
        p[0] = [p[1], p[3]]

    def p_entity_list_extend(self, p):
        "entity_list : entity_list COMMA ENTITY"
        p[1].append(p[3])
        p[0] = p[1]

    def p_deactivate(self, p):
        "deactivate : DEACTIVATE ENTITY"
        p[0] = SetActivationState([self.getEntity(p[2])], False)

    def p_deactivate_list(self, p):
        "deactivate : DEACTIVATE entity_list"
        p[0] = SetActivationState([self.getEntity(ent) for ent in p[2]], False)

    def p_destroy(self, p):
        "destroy : DESTROY ENTITY"
        p[0] = Destroy(p[2])

    def p_note(self, p):
        """
        note : NOTE OVER ENTITY STRING
        note : NOTE LEFT OF ENTITY STRING
        note : NOTE RIGHT OF ENTITY STRING
        """
        if len(p) == 5:
            p[0] = Note(p[2], self.getEntity(p[3]), p[4])
        else:
            p[0] = Note(p[2], self.getEntity(p[4]), p[5])

    def p_error(self, p):
        s = self.code.rfind("\n", 0, p.lexpos) + 1
        e = self.code.find("\n", p.lexpos )
        ref = self.code[s:e]
        print "Syntax error at '%s' on line %d pos %d" % (p.value, p.lineno, p.lexpos)
        print "%s" % repr(ref)
        print " %s^" % (" " * (p.lexpos - s))

    def _buildlexer(self, **kwargs):
        self.lexer = lex.lex(module=self, **kwargs)

    def testLexer(self, data):
        self._buildlexer()
        self.lexer.input(data)
        while True:
            tok = self.lexer.token()
            if not tok:
                break
            print tok

    def parse(self, code):
        self.code = code
        self._buildlexer()
        self.parser = yacc.yacc(module=self)
        res = self.parser.parse(code, lexer=self.lexer)
        for i, entity in enumerate(self.knownEntities.values()):
            res.operations.insert(i, DeclareEntity(entity))
        return res

CODE = """activate d
# First
activate a activate b
a->b "Hello"
# Comment "that might be confused with a string"
b<-a "Back at yea" a->c "Howdy"
loop 2 {
    deactivate b activate c
    loop 100 {
        c<-a "Who are you?" # comment
        c->c "Who am I? Who are you?" # comment
        c<-a "I asked first, Who are you?"
    }
    deactivate c deactivate a
}
destroy b
opt "bla bla bla" {
    g->d "A"
    note over g
    g<-d "B"
    note left of d
    alt "gogog" {
        g->d "C"
        note right of d
        g<-d "B"
    } else "gogog" {
        g->d "D"
        g<-d "EB"
    }
}
"""

def _test():
    print CODE
    parser = SegeParser()
    print "LEXing..."
    parser.testLexer(CODE)
    print "YACCing..."
    print parser.parse(CODE)

def parse(code):
    parser = SegeParser()
    return parser.parse(code)

if __name__ == "__main__":
    _test()

