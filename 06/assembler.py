#!/usr/bin/env python
import re
import sys
from os import path

class ParseError(Exception):
  pass

class AssembleError(Exception):
  pass


class SymbolTableBuilder:
  def __init__(self, parser):
    self._parser = parser

  def build(self):
    count = 0
    symbol_table = SymbolTable()

    while self._parser.has_more_commands():
      self._parser.advance()
      if self._parser.command_type() != 'L_COMMAND':
        count += 1
      else:
        symbol_table.add_entry(self._parser.symbol(), count)
    return symbol_table

class Assembler:
  _WORD_LENGTH = 16

  def __init__(self, filename):
    self._parser = Parser(filename)
    self._symbol_table = SymbolTableBuilder(self._parser).build()
    self._parser.reset()

    self._assembled = open(self._determine_assembled_filename(filename), 'w')
    self._assemble()

    self._parser.close()
    self._assembled.close()

  '''If assembly filename ends in .asm, output file will change this extension to .hack. Otherwise,
  .hack extension will simply be appended to assembly filename.'''
  def _determine_assembled_filename(self, assembly_filename):
    assembled_ext = '.hack'
    assembled_filename = re.compile(r'\.asm$', re.IGNORECASE).sub(assembled_ext, assembly_filename)
    if not assembled_filename.endswith(assembled_ext):
      assembled_filename += assembled_ext
    return assembled_filename

  def _assemble(self):
    while self._parser.has_more_commands():
      self._parser.advance()
      command_type = self._parser.command_type()
      if command_type == 'L_COMMAND':
        continue

      command = {
        'A_COMMAND': self._build_a_command,
        'C_COMMAND': self._build_c_command,
      }[command_type]()
      self._assembled.write(command + '\n')

  def _build_a_command(self):
    # Need extra bit to indicate instruction is an A instruction
    symbol = self._parser.symbol()
    if symbol.isdigit():
      return self._build_a_command_constant(symbol)
    # Note that no checking of the symbol is done to ensure it conforms to allowed symbol
    # characters. It may, for example start with a digit, which is against the spec.
    else:
      return self._build_a_command_reference(symbol)

  def _build_a_command_constant(self, constant):
    max_length = self._WORD_LENGTH - 1
    binary_value = self._convert_denary_to_binary(constant)
    if len(binary_value) > max_length:
      raise AssembleError('Constant %s cannot fit in %s available bits' % (constant, max_length))
    # Pad with leading zeroes
    return '0%s%s' % ('0'*(max_length - len(binary_value)), binary_value)

  def _build_a_command_reference(self, symbol):
    if not self._symbol_table.contains(symbol):
      self._symbol_table.add_variable(symbol)
    address = self._symbol_table.get_address(symbol)
    return self._build_a_command_constant(address)

  def _build_c_command(self):
    return '%s%s%s%s' % (
      '111',
       Code.comp(self._parser.comp()),
       Code.dest(self._parser.dest()),
       Code.jump(self._parser.jump()),
    )

  # I'm sure Python's standard library includes a means of doing this, but I'm rolling my own since
  # the intent of this project is to learn.
  def _convert_denary_to_binary(self, i):
    binary = ''
    i = int(i)
    while True:
      binary = '%s%s' % (i % 2, binary)
      i /= 2
      if i == 0:
        return binary


class Parser:
  def __init__(self, filename):
    self._file = open(filename)

  def has_more_commands(self):
    return self._file.tell() - path.getsize(self._file.name) != 0

  def advance(self):
    while self.has_more_commands():
      command = self._file.readline()
      # Strip comment from line if present, as well as any extraneous whitespace.
      command = command[:command.find('//')].strip()
      # Read until non-whitespace line found.
      if command:
        self._command = command
        break

  def command_type(self):
    if self._command.startswith('@'):
      return 'A_COMMAND'
    elif self._command.startswith('('):
      return 'L_COMMAND'
    else:
      return 'C_COMMAND'

  def symbol(self):
    return re.search(r'[(@]([a-zA-Z0-9_.$:]+)\)?', self._command).group(1)

  def dest(self):
    return self._parse_mnemonic('dest')

  def comp(self):
    return self._parse_mnemonic('comp')

  def jump(self):
    return self._parse_mnemonic('jump')

  def close(self):
    self._file.close()

  def reset(self):
    self._file.seek(0)
 
  def _parse_mnemonic(self, kind):
    components = self._split_c_command()
    if components[kind] not in CInstructionCodes.CODES[kind]:
      raise ParseError('Invalid %s: %s' % (kind, components[kind]))
    return components[kind]

  def _split_c_command(self):
    # Regular expressions quickly turn into a quaqmire for this task. This code is slightly longer,
    # but clearer.
    parts = self._command.split('=', 1)
    if len(parts) > 1:
      dest, comp = parts
    else:
      dest, comp = None, parts[0]

    parts = comp.split(';', 1)
    if len(parts) > 1:
      comp, jump = parts
    else:
      comp, jump = parts[0], None

    return {'dest': dest, 'comp': comp, 'jump': jump}


class Code:
  @staticmethod
  def dest(mnemonic):
    return CInstructionCodes.CODES['dest'][mnemonic]

  @staticmethod
  def comp(mnemonic):
    return CInstructionCodes.CODES['comp'][mnemonic]

  @staticmethod
  def jump(mnemonic):
    return CInstructionCodes.CODES['jump'][mnemonic]


class SymbolTable:
  def __init__(self):
    self._table = {
      'SP':     0,
      'LCL':    1,
      'ARG':    2,
      'THIS':   3,
      'THAT':   4,
      'SCREEN': 0x4000,
      'KBD':    0x6000,
    }
    # Add R0 through R15 to symbol table.
    for i in range(16):
      self._table['R%s' % i] = i
    # Base address for previously undeclared variable symbols. By default, set to first address
    # after predefined symbols.
    self._variable_base = 16

  def add_entry(self, symbol, address):
    self._table[symbol] = address

  def add_variable(self, symbol):
    self.add_entry(symbol, self._variable_base)
    self._variable_base += 1

  def contains(self, symbol):
    return symbol in self._table

  def get_address(self, symbol):
    return self._table[symbol]


class CInstructionCodes:
  CODES = {
    'dest': {
      None:  '000',
      'M':   '001',
      'D':   '010',
      'MD':  '011',
      'A':   '100',
      'AM':  '101',
      'AD':  '110',
      'AMD': '111',
    },

    'comp': {
      '0':   '0101010',
      '1':   '0111111',
      '-1':  '0111010',
      'D':   '0001100',
      'A':   '0110000',
      '!D':  '0001101',
      '!A':  '0110001',
      '-D':  '0001111',
      '-A':  '0110011',
      'D+1': '0011111',
      'A+1': '0110111',
      'D-1': '0001110',
      'A-1': '0110010',
      'D+A': '0000010',
      'D-A': '0010011',
      'A-D': '0000111',
      'D&A': '0000000',
      'D|A': '0010101',
      'M':   '1110000',
      '!M':  '1110001',
      '-M':  '1110011',
      'M+1': '1110111',
      'M-1': '1110010',
      'D+M': '1000010',
      'D-M': '1010011',
      'M-D': '1000111',
      'D&M': '1000000',
      'D|M': '1010101',
    },

    'jump': {
      None:  '000',
      'JGT': '001',
      'JEQ': '010',
      'JGE': '011',
      'JLT': '100',
      'JNE': '101',
      'JLE': '110',
      'JMP': '111',
    },
  }


if __name__ == '__main__':
  Assembler(sys.argv[1])
