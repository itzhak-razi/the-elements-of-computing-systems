#!/usr/bin/env python
import os
import re
import sys

class Translator:
  def __init__(self, path):
    # Find vm_files before initializing code writer in case the former process raises an exception.
    vm_files = self._get_vm_file_paths(path)
    self._code_writer = CodeWriter(path)
    for vm_file in vm_files:
      self._process_vm_file(vm_file)
    self._code_writer.close()

  def _get_vm_file_paths(self, path):
    if os.path.isdir(path):
      vm_files = [os.path.join(path, f) for f in os.listdir(path) if f.lower().endswith('.vm')]
      if len(vm_files) == 0:
        raise IOError('No .vm files in directory %s' % path)
    elif os.path.isfile(path):
      vm_files = [path]
    else:
      raise IOError('%s is not a file or directory' % path)

    return vm_files

  def _process_vm_file(self, file_path):
    parser = Parser(file_path)
    self._code_writer.set_vm_filename(file_path)

    while parser.has_more_commands():
      parser.advance()
      if parser.command_type() == 'C_ARITHMETIC':
        self._code_writer.write_arithmetic(parser.command())
      elif parser.command_type() in ('C_PUSH', 'C_POP'):
        self._code_writer.write_push_pop(parser.command(), parser.arg1(), parser.arg2())
    parser.close()


class ParseError(Exception):
  pass


class CodeWriteError(Exception):
  pass


class Parser:
  def __init__(self, filename):
    self._file = open(filename)
    # Must read "next" command to allow has_more_commands() to work before call to advance().
    self._read_next_command()

  def has_more_commands(self):
    return self._next_command != None

  def advance(self):
    self._parse_command(self._next_command)
    self._read_next_command()
  
  def _read_next_command(self):
    while True:
      command = self._file.readline()
      # EOF
      if not command:
        self._next_command = None
        break

      # Strip comment from line if present, as well as any extraneous whitespace.
      command = command[:command.find('//')].strip()
      # Read until non-whitespace line found.
      if command:
        self._next_command = command
        break

  def _parse_command(self, command):
    tokens = command.split()
    tokens = [e.lower() for e in tokens]
    # Ensure at least three elements in tokens, in case command took < 2 arguments.
    tokens.extend([None, None])
    self._command, self._arg1, self._arg2 = tokens[:3]

  def command_type(self):
    types = {
      'push': 'C_PUSH',
      'pop':  'C_POP'
    }
    for arithmetic in ArithmeticAndLogicalOpsTable.all_ops():
      types[arithmetic] = 'C_ARITHMETIC'

    if self._command in types:
      return types[self._command]
    raise ParseError('Unknown command: %s' % self._command)

  def command(self):
    return self._command

  def arg1(self):
    if not self._arg1:
      raise ParseError('No first argument present for %s' % self.command_type())
    return self._arg1

  def arg2(self):
    if not self._arg2:
      raise ParseError('No second argument present for %s' % self.command_type())
    return self._arg2

  def close(self):
    self._file.close()


class ArithmeticAndLogicalOpsTable:
  _OPS = {
    'binary_transformation': {
      'add': '+',
      'sub': '-',
      'and': '&',
      'or':  '|',
    },

    'unary_transformation': {
      'not': '!',
      'neg': '-',
    },

    'binary_logical': {
      'gt': 'JGT',
      'lt': 'JLT',
      'eq': 'JEQ',
    }
  }

  @classmethod
  def all_ops(cls):
    ops = []
    for category in cls._OPS:
      for op in cls._OPS[category]:
        ops.append(op)
    return ops

  @classmethod
  def categories(cls):
    return cls._OPS.keys()

  @classmethod
  def ops_with_symbols(cls, category):
    return cls._OPS[category]

  @classmethod
  def symbol(cls, category, op):
    return cls._OPS[category][op]


class CodeWriter:
  _SEGMENT_BASES = {
    'dynamic': {
      'local':    'LCL',
      'argument': 'ARG',
      'this':     'THIS',
      'that':     'THAT',
    },

    'fixed': {
      'temp':    'R5',
      'pointer': 'THIS',
    }
  }

  _VM_EXTENSION_REGEX = re.compile(r'\.vm$', re.IGNORECASE)

  def __init__(self, vm_path):
    self._output = open(self._determine_assembly_filename(vm_path), 'w')
    self._init_stack_pointer()
    self._logical_label_counter = 0

  '''If VM file's name ends in .vm, output file will change this extension to .asm. Otherwise,
  .asm extension will simply be appended to assembly filename.'''
  def _determine_assembly_filename(self, vm_path):
    assembly_ext = '.asm'
    assembly_filename = self._VM_EXTENSION_REGEX.sub(assembly_ext, vm_path)
    if not assembly_filename.endswith(assembly_ext):
      assembly_filename += assembly_ext
    return assembly_filename

  def _init_stack_pointer(self):
    self._write_comment('Initialize stack pointer')
    self._write_instructions([
      '@256',
      'D=A',
      '@SP',
      'M=D'
    ])
    self._write_newline()

  def set_vm_filename(self, vm_file_path):
    vm_file_path = os.path.basename(vm_file_path)
    self._vm_basename = self._VM_EXTENSION_REGEX.sub('', vm_file_path)

  def write_arithmetic(self, command):
    for category in ArithmeticAndLogicalOpsTable.categories():
      if command in ArithmeticAndLogicalOpsTable.ops_with_symbols(category):
        self._write_comment(command)
        method = getattr(self, '_write_arithmetic_%s' % category)
        method(ArithmeticAndLogicalOpsTable.symbol(category, command))
        self._write_newline()
        break
    else:
      raise CodeWriteError('Unknown arithmetic or logical command: %s' % command)

  def write_push_pop(self, command, segment, index):
    command_with_args = ' '.join( (command, segment, index) )
    self._write_comment(command_with_args)

    if command == 'push' and segment == 'constant':
      self._push_constant(index)
    elif segment in self._SEGMENT_BASES['fixed'].keys() + self._SEGMENT_BASES['dynamic'].keys():
      self._push_pop_variable(command, segment, index)
    elif segment == 'static':
      self._push_pop_static(command, index)
    else:
      raise CodeWriteError('Unknown push/pop command: %s' % command_with_args)

    self._write_newline()

  def _push_pop_static(self, command, index):
    symbol = '%s.%s' % (self._vm_basename, index)
    if command == 'push':
      self._write_instructions([
        '@%s' % symbol,
        'D=M'
      ])
      self._push_from('D')
    elif command == 'pop':
      self._pop_into('D')
      self._write_instructions([
        '@%s' % symbol,
        'M=D'
      ])
    else:
      raise CodeWriteError('Unknown push/pop command: %s' % command)

  def _write_arithmetic_binary_transformation(self, op):
    self._pop_into('D')
    self._pop_into('A')
    self._write_instruction('D=A%sD' % op)
    self._push_from('D')

  def _write_arithmetic_unary_transformation(self, op):
    self._write_instructions([
      '@SP',
      'A=M-1',
      'M=%sM' % op,
    ])

  def _write_arithmetic_binary_logical(self, jump_type):
    self._logical_label_counter += 1
    jump_label = 'LOGICAL_JUMP_%d' % self._logical_label_counter

    self._pop_into('D')
    self._pop_into('A')
    self._write_instruction('D=A-D')
    self._write_instructions([
      '@%s_TRUE' % jump_label,
      'D;%s' % jump_type
    ])
    self._push_boolean(False)
    self._write_instructions([
      '@%s_END' % jump_label,
      '0;JMP',
      '(%s_TRUE)' % jump_label
    ])
    self._push_boolean(True)
    self._write_instruction('(%s_END)' % jump_label)

  def _push_constant(self, constant):
    self._write_instructions([
      '@%s' % constant,
      'D=A',
      '@SP',
      'M=M+1',
      'A=M-1',
      'M=D'
    ])

  def _push_pop_variable(self, command, segment, index):
    if command == 'push':
      self._calculate_address('A', segment, index)
      self._write_instruction('D=M')
      self._push_from('D')
    elif command == 'pop':
      self._calculate_address('D', segment, index)
      self._write_instructions([
        '@R13',
        'M=D'
      ])
      self._pop_into('D')
      self._write_instructions([
        '@R13',
        'A=M',
        'M=D'
      ])
    else:
      raise CodeWriteError('Command is neither push nor pop: %s' % command)

  def _calculate_address(self, dest_reg, segment, offset):
    if segment in self._SEGMENT_BASES['dynamic']:
      base_location = self._SEGMENT_BASES['dynamic'][segment]
      base_value = 'M'
    elif segment in self._SEGMENT_BASES['fixed']:
      base_location = self._SEGMENT_BASES['fixed'][segment]
      base_value = 'A'

    self._write_instructions([
      '@%s' % offset,
      'D=A',
      '@%s' % base_location,
      '%s=%s+D' % (dest_reg, base_value)
    ])

  # Side effect: overwrites A register, so if you're going to pop into both D and A, do A last.
  def _pop_into(self, register):
    self._write_instructions([
      '@SP',
      'M=M-1',
      'A=M',
      '%s=M' % register
    ])

  def _push_from(self, register):
    self._write_instructions([
      '@SP',
      'M=M+1',
      'A=M-1',
      'M=%s' % register
    ])

  def _push_boolean(self, bool):
    self._write_instructions([
      '@SP',
      'M=M+1',
      'A=M-1',
      'M=%d' % (0, -1)[bool]
    ])

  def _write(self, s):
    self._output.write(s + '\n')

  def _write_newline(self):
    self._write('')

  def  _write_comment(self, comment):
    self._write('// %s' % comment)

  def _write_instruction(self, command):
    self._write_instructions([command])

  def _write_instructions(self, commands):
    # Indent command unless it is a label.
    commands = [[2*' ', ''][command.startswith('(')] + command for command in commands]
    self._write('\n'.join(commands))

  def close(self):
    self._write_comment('Enter infinite loop to terminate useful work')
    self._write_instructions([
      '(TERMINAL_INFINITE_LOOP)',
      '@TERMINAL_INFINITE_LOOP',
      '0;JMP'
    ])
    self._output.close()


if __name__ == '__main__':
  Translator(sys.argv[1])
