#include <stdio.h>

/* Forward declaration */
void bye();

int main()
{
  printf("Oh hai world\n");
  int i = 0;
  for(i = 0; i < 5; i++){
    printf("i = %d\n", i);
  }
  printf("i = %d\n", i);
  printf("i + 8 = %d\n", i + 8);
  bye();
}
