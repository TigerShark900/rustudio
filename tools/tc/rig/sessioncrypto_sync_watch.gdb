set pagination off
set debuginfod enabled off
set print thread-events off
handle SIGPIPE nostop noprint pass
handle SIGUSR1 nostop noprint pass
handle SIGUSR2 nostop noprint pass

# After Studio's 0x90 builder, before its send.
break *0x14609f844
commands
  silent
  printf "M90_SERIALIZED rbp=%#lx\n", $rbp
  dump binary memory /home/user/.cache/rustudio-dev/tc/keys/sessioncrypto-watch/m90-stack.bin $rbp-0x100 $rbp+0x100
  set $p = *(unsigned long long*)($rbp-0x20)
  printf "M90_DATA candidate=%#lx\n", $p
  if $p > 0x10000
    dump binary memory /home/user/.cache/rustudio-dev/tc/keys/sessioncrypto-watch/m90-data.bin $p $p+0x4000
  end
  continue
end

# Immediately after Studio combines the fresh 0x92 random value and mask.
break *0x1460915d2
commands
  silent
  printf "M92_COMBINED value=%#lx random=%#lx\n", $rcx, $rbx
  detach
  quit
end
continue
