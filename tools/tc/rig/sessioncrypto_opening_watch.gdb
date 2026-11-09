set pagination off
set debuginfod enabled off
set print thread-events off
handle SIGPIPE nostop noprint pass
handle SIGUSR1 nostop noprint pass
handle SIGUSR2 nostop noprint pass

# Immediately after Studio's 0x8a SessionId builder, before the packet is sent.
break *0x14609f1a2
commands
  silent
  printf "M8A_SERIALIZED rbp=%#lx\n", $rbp
  x/6gx $rbp-0x80
  dump binary memory /home/user/.cache/rustudio-dev/tc/keys/sessioncrypto-watch/m8a-stack.bin $rbp-0x100 $rbp+0x100
  set $p = *(unsigned long long*)($rbp-0x70)
  printf "M8A_DATA candidate=%#lx\n", $p
  if $p > 0x10000
    dump binary memory /home/user/.cache/rustudio-dev/tc/keys/sessioncrypto-watch/m8a-data.bin $p $p+0x4000
  end
  detach
  quit
end
continue
