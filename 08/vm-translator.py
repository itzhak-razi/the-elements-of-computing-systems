#!/usr/bin/env python
import os
import re
import sys

class Translator:
  def __init__(self, path):
    self._init_command_args()
    # Find vm_files before initializing code writer in case the former process raises an exception.
    vm_files = self._get_vm_file_paths(path)
    self._code_writer = CodeWriter(path)

    for vm_file in vm_files:
      self._process_vm_file(vm_file)
    self._code_writer.close()

  def _init_command_args(self):
    self._COMMAND_ARGS = {
      'arithmetic': lambda parser: (parser.command(),),
      'return':     lambda parser: tuple()
    }
    for command in ('push', 'pop', 'call', 'function'):
      self._COMMAND_ARGS[command] = lambda parser: (parser.arg1(), parser.arg2())
    for command in ('label', 'goto', 'if'):
      self._COMMAND_ARGS[command] = lambda parser: (parser.arg1(),)

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
      args = self._COMMAND_ARGS[parser.command_type()](parser)
      command_writer = getattr(self._code_writer, 'write_%s' % parser.command_type())
      command_writer(parser.command_with_args(), *args)
    parser.close()


class ParseError(Exception):
  pass


class CodeWriteError(Exception):
  pass


class Parser:
  def __init__(self, filename):
    self._init_types()
    self._file = open(filename)
    # Must read "next" command to allow has_more_commands() to work before call to advance().
    self._read_next_command()

  def _init_types(self):
    self._types = { 'if-goto':  'if' } # Special case -- method name "write_if-goto" not valid in Python.
    for type in ('push', 'pop', 'label', 'goto', 'function', 'return', 'call'):
      self._types[type] = type
    for arithmetic in ArithmeticAndLogicalOpsTable.all_ops():
      self._types[arithmetic] = 'arithmetic'

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
    # Ensure at least three elements in tokens, in case command took < 2 arguments.
    tokens.extend([None, None])
    self._command, self._arg1, self._arg2 = tokens[:3]

  def command_type(self):
    if self._command in self._types:
      return self._types[self._command]
    raise ParseError('Unknown command: %s' % self._command)

  def command(self):
    return self._command

  def command_with_args(self):
    '''Return normalized command (that is, excess whitespace stripped from between args), with any args present.'''
    return ' '.join([str(e) for e in self._command, self._arg1, self._arg2 if e])

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
    self._unique_id = 0
    self._line_counter = 0
    self._current_function = 'no_function'
    self._output = open(self._determine_assembly_path(vm_path), 'w')
    self.write_init()

  # Place assembly file in same directory as VM files, regardless of whether input argument is a
  # directory or a VM file.
  #
  # BUG: if file with .asm extension is passed as input filename on command line, the translation
  # process will succeed. This occurs because the file is truncated as part of the output process,
  # and since it is then empty and no commands are read (as opposed to the assembly commands that
  # were there before truncation), translation succeds.
  def _determine_assembly_path(self, vm_path):
    # Remove trailing slash if present so that basename will never be empty.
    vm_path = os.path.normpath(vm_path)
    # Convert "." to proper directory name -- otherwise, output file will be "..asm".
    vm_path = os.path.realpath(vm_path)
    vm_basename = os.path.basename(vm_path)

    # If .vm extension present, replace with .asm; otherwise, append .asm.
    assembly_ext = '.asm'
    assembly_filename = self._VM_EXTENSION_REGEX.sub(assembly_ext, vm_basename)
    if not assembly_filename.endswith(assembly_ext):
      assembly_filename += assembly_ext

    # Place .asm file in same directory as VM files.
    if os.path.isdir(vm_path):
      return os.path.join(vm_path, assembly_filename)
    else:
      return os.path.join(os.path.dirname(vm_path), assembly_filename)

  def set_vm_filename(self, vm_file_path):
    vm_file_path = os.path.basename(vm_file_path)
    self._vm_basename = self._VM_EXTENSION_REGEX.sub('', vm_file_path)

  def _command(f):
    '''Write comment listing command, as well as blank line separator.'''
    def wrapped(self, *args, **kwargs):
      comment = args[0]
      self._write_comment(comment)
      f(self, *args[1:], **kwargs)
      self._write_newline()
    return wrapped

  @_command
  def _init_stack_pointer(self):
    self._write_instructions([
      '@256',
      'D=A',
      '@SP',
      'M=D'
    ])

  # BUG: VM files must include a Sys.init function, or test scripts will fail. I should test for
  # existence of Sys.init function and call it only if present, but I don't.
  def write_init(self):
    self._init_stack_pointer('Initialize stack pointer')
    init_function = 'Sys.init'
    self.write_call('call %s' % init_function, init_function, 0)

  @_command
  def write_arithmetic(self, command):
    for category in ArithmeticAndLogicalOpsTable.categories():
      if command in ArithmeticAndLogicalOpsTable.ops_with_symbols(category):
        method = getattr(self, '_write_arithmetic_%s' % category)
        method(ArithmeticAndLogicalOpsTable.symbol(category, command))
        break
    else:
      raise CodeWriteError('Unknown arithmetic or logical command: %s' % command)

  @_command
  def write_push(self, segment, index):
    self._write_push_pop('push', segment, index)

  @_command
  def write_pop(self, segment, index):
    self._write_push_pop('pop', segment, index)

  def _calculate_label(self, label):
    return '%s$%s' % (self._current_function, label)

  @_command
  def write_label(self, label):
    self._write_instruction('(%s)' % self._calculate_label(label))

  @_command
  def write_goto(self, label):
    self._write_instructions([
      '@%s' % self._calculate_label(label),
      '0;JMP'
    ])

  @_command
  def write_if(self, label):
    self._pop_into('D')
    self._write_instructions([
      '@%s' % self._calculate_label(label),
      'D;JNE'
    ])

  @_command
  def write_call(self, function_name, num_args):
    return_address = 'return_from_%s_%s' % (function_name, self._generate_unique_id())

    # push return_address
    self._write_instructions([
      '@%s' % return_address,
      'D=A',
    ])
    self._push_from('D')

    # push LCL, ARG, THIS, THAT
    for address in ('LCL', 'ARG', 'THIS', 'THAT'):
      self._write_instructions([
        '@%s' % address,
        'D=M',
      ])
      self._push_from('D')

    # ARG = SP - (num_args + 5)
    self._write_instructions([
      '@%s' % num_args, # D = num_args + 5
      'D=A',
      '@5',
      'D=A+D',

      '@SP',            # ARG = SP - D
      'D=M-D',
      '@ARG',
      'M=D'
    ])

    # LCL = SP
    self._write_instructions([
      '@SP',
      'D=M',
      '@LCL',
      'M=D'
    ])

    # goto function_name
    self._write_instructions([
      '@%s' % function_name,
      '0;JMP'
    ])

    self._write_instruction('(%s)' % return_address)

  @_command
  def write_function(self, function_name, num_locals):
    self._current_function = function_name

    locals_start, locals_end = '%s_fill_locals_start' % function_name, '%s_fill_locals_end' % function_name
    # Declare label and then push zero to stack num_locals times.
    self._write_instructions([
      '(%s)' % function_name, 

      '@%s' % num_locals,     # *R13 = num_locals
      'D=A',
      '@R13',
      'M=D',

      '(%s)' % locals_start, # while(--(*R13) >= 0) push(0);
      '@R13',
      'MD=M-1',

      '@%s' % locals_end,
      'D;JLT'
    ])
    self._push_constant(17)
    self._write_instructions([
      '@%s' % locals_start,
      '0;JMP',
      '(%s)' % locals_end
    ])

  @_command
  def write_return(self):
    # R14 = RET                # Store return address in temporary variable
    # *ARG = pop()             # Put return value of function at beginning of frame of called function
    # SP = ARG + 1             # Reposition SP so it points to just after return value of called function
    # FRAME = LCL              # Create temporary value pointing to beginning of called function's frame
    # THAT = *(FRAME - 1)      # Restore THAT of calling function
    # THIS = *(FRAME - 2)      # Restore THIS of calling function
    # ARG  = *(FRAME - 3)      # Restore ARG of calling function
    # LCL  = *(FRAME - 4)      # Restore LCL of calling function
    # goto RET                 # Jump to point right after where caller called function

    # Store return address in temporary variable.
    # Note that this is necessary -- I tried to be clever and retrieve the return address from
    # *(FRAME - 5) only when I needed it for the GOTO, but if zero arguments were passed to the function from
    # which we are returning, then ARG will point to the same memory location where the return address
    # is stored. In such a case, when we put the return value of the function into the memory
    # location pointed to by ARG, we overwrite the return address. (I should have figured this out
    # from the diagram on p. 162 of the book. Because I didn't, I spent six hours debugging. Bah.)
    self._write_instructions([
      '@5', # R14 = *(LCL - 5)
      'D=A',
      '@LCL',
      'A=M-D',
      'D=M',
      '@R14',
      'M=D'
    ])

    # Put return value of function at beginning of frame of called function
    self._pop_into('D')
    self._write_instructions([
      '@ARG',
      'A=M',
      'M=D'
    ])

    # Reposition SP so it points to just after return value of called function
    self._write_instructions([
      '@ARG',
      'D=M+1',
      '@SP',
      'M=D'
    ])

    # Restore THAT, THIS, ARG, and LCL of calling function
    self._write_instructions([
      '@LCL', # *R13 = *LCL
      'D=M',
      '@R13',
      'M=D'
    ])
    for address in ('THAT', 'THIS', 'ARG', 'LCL'):
      # *address = M[ --(*R13) ]
      self._write_instructions([
        '@R13',
        'AM=M-1',
        'D=M',

        '@%s' % address,
        'M=D'
      ])

    # Jump to point right after where caller called function
    self._write_instructions([
      '@R14',
      'A=M',
      '0;JMP'
    ])

  def _write_push_pop(self, command, segment, index):
    command_with_args = ' '.join( (command, segment, index) )

    if command == 'push' and segment == 'constant':
      self._push_constant(index)
    elif segment in self._SEGMENT_BASES['fixed'].keys() + self._SEGMENT_BASES['dynamic'].keys():
      self._push_pop_variable(command, segment, index)
    elif segment == 'static':
      self._push_pop_static(command, index)
    else:
      raise CodeWriteError('Unknown push/pop command: %s' % command_with_args)

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
      raise CodeWriteError('Unknown static push/pop command: %s' % command)

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

  def _generate_unique_id(self):
    self._unique_id += 1
    return self._unique_id

  def _write_arithmetic_binary_logical(self, jump_type):
    jump_label = 'LOGICAL_JUMP_%d' % self._generate_unique_id()

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
      'AM=M-1',
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
    for cmd in commands:
      is_label = cmd.startswith('(')

      # Insert line number if command is not label to allow for easy correlation with commands
      # displayed in CPU Emulator.
      # Also, indent command unless it is a lbel.
      if not is_label:
        spaces = ' '*(60 - len(cmd))
        cmd = '  %s %s// Line %d' % (cmd, spaces, self._line_counter)
        self._line_counter += 1
      self._write(cmd)

  def close(self):
     self._output.close()


if __name__ == '__main__':
  if len(sys.argv) != 2:
    sys.exit('Usage: %s [VM file, or directory containing VM files]' % sys.argv[0])
  Translator(sys.argv[1])
