set pagination off
set debuginfod enabled off
set print thread-events off
handle SIGPIPE nostop noprint pass
handle SIGUSR1 nostop noprint pass
handle SIGUSR2 nostop noprint pass

break *0x14609e5a0
commands
  silent
  printf "A8_BUILDER rcx=%#lx\n", $rcx
  bt 14
  continue
end

break *0x1461de980
commands
  silent
  printf "A7_BLOCK_BUILDER rcx=%#lx rdx=%#lx\n", $rcx, $rdx
  bt 20
  dump binary memory /home/user/.cache/rustudio-dev/tc/keys/sessioncrypto-watch/a7-object.bin $rcx $rcx+0x180
  dump binary memory /home/user/.cache/rustudio-dev/tc/keys/sessioncrypto-watch/a7-stack.bin $rsp $rsp+0x400
  detach
  quit
end

break *0x1461de8d0
commands
  silent
  printf "A7_BYTE_BUILDER rcx=%#lx rdx=%#lx\n", $rcx, $rdx
  bt 20
  dump binary memory /home/user/.cache/rustudio-dev/tc/keys/sessioncrypto-watch/a7-object.bin $rcx $rcx+0x180
  dump binary memory /home/user/.cache/rustudio-dev/tc/keys/sessioncrypto-watch/a7-stack.bin $rsp $rsp+0x400
  detach
  quit
end

continue
