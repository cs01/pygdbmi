#include <stdio.h>

struct my_type_t {
    int a;
    float b;
    struct {
        size_t c;
        double d;
    };
};

/* Forward declaration */
void bye();

int main()
{
    printf("oh hai world\n");
    struct my_type_t myvar= {
        .a = 1,
        .b = 1.2,
        .c = 4,
        .d = 6.7
    };
    int i = 0;
    for(i = 0; i < 1; i++){
        printf("i = %d\n", i);
    }
    bye();
}
